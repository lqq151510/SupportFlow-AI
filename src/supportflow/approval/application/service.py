"""操作申请（审批）用例编排。

PLAN §5 的三条语义在这里落地：

1. **申请**保存不可变的动作参数与「发起时的工单版本」；同一运行的同一动作类型
   至多一个待审批申请（由数据库部分唯一索引保证，重放返回既有申请）。
2. **决策**只有「待审批且未过期」可处理；过期、已处理、版本变化都必须能被调用方
   区分 —— 分别对应 ``action_request_expired`` / ``action_request_not_pending`` /
   ``ticket_version_changed``。
3. **执行与记账在同一个事务**：本服务不自己提交，由 ``session_scope`` 统一提交，
   因此「执行了但没记账」在结构上不可能发生。

账本的幂等键由申请 ID 派生（``action-request:<id>``），配合 ``action_ledger`` 上的
两个唯一约束，重复审批、任务重投或检查点重放都只产生一次业务效果。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from uuid import UUID

from supportflow.approval.domain.models import (
    ACTION_REQUEST_TTL,
    ActionDecision,
    ActionLedgerEntry,
    ActionRequest,
    ActionRequestStatus,
    ActionType,
    NewActionRequest,
)
from supportflow.approval.domain.ports import (
    ActionLedgerPort,
    ActionRequestRepositoryPort,
    RunOutcomePort,
    TicketActionPort,
)
from supportflow.identity.domain.models import Principal
from supportflow.shared.clock import utcnow
from supportflow.shared.errors import (
    ActionRequestExpired,
    ActionRequestNotFound,
    ActionRequestNotPending,
    Forbidden,
    InvalidRequest,
    NotFound,
    TicketVersionChanged,
)

logger = logging.getLogger(__name__)

#: 账本幂等键前缀。由申请 ID 派生，因此同一次申请永远得到同一个键。
LEDGER_KEY_PREFIX = "action-request"

#: 决策被拒的原因。刻意用稳定字符串而不是自由文本。
BLOCKED_REJECTED = "rejected"


class ActionApprovalService:
    def __init__(
        self,
        requests: ActionRequestRepositoryPort,
        ledger: ActionLedgerPort,
        tickets: TicketActionPort,
        runs: RunOutcomePort | None = None,
        *,
        ttl: timedelta = ACTION_REQUEST_TTL,
    ) -> None:
        self._requests = requests
        self._ledger = ledger
        self._tickets = tickets
        #: 决策后推进运行终态。``None`` 仅用于不关心运行的测试。
        self._runs = runs
        self._ttl = ttl

    # --- 申请 ---------------------------------------------------------------

    def request_action(
        self,
        principal: Principal,
        *,
        ticket_id: UUID,
        run_id: UUID,
        action_type: ActionType,
        parameters: dict[str, object],
        ticket_version: int,
        target_assignee_id: UUID | None = None,
    ) -> ActionRequest:
        """创建操作申请。**不做动作本身** —— HIGH_RISK 动作只能申请（AGENTS.md §5）。

        重放语义：同一运行 + 同一动作类型已有待审批申请时直接返回它，
        不再创建第二条（数据库的部分唯一索引是最终保证）。
        """
        self._require_staff(principal)
        self._validate(action_type, target_assignee_id)

        existing = self._requests.find_pending(run_id, action_type)
        if existing is not None:
            logger.info(
                "复用待审批申请：run_id=%s action=%s request_id=%s",
                run_id,
                action_type.value,
                existing.id,
            )
            return existing

        current = self._tickets.current_version(ticket_id)
        if current is None:
            raise NotFound("工单不存在")
        if current != ticket_version:
            # 从源头拒绝：创建一条注定作废的申请只会浪费审批人的注意力。
            raise TicketVersionChanged(
                f"工单版本已变化（申请基于 {ticket_version}，当前 {current}）"
            )

        return self._requests.add(
            NewActionRequest(
                ticket_id=ticket_id,
                run_id=run_id,
                action_type=action_type,
                parameters=parameters,
                ticket_version=ticket_version,
                target_assignee_id=target_assignee_id,
            ),
            expires_at=utcnow() + self._ttl,
        )

    # --- 系统侧提议（Agent Worker 的运行上下文） ----------------------------

    def propose_by_system(
        self,
        *,
        ticket_id: UUID,
        run_id: UUID,
        action_type: str,
        reason: str,
    ) -> dict[str, object]:
        """运行内的模型提议。**不做人员授权**：调用者是 Worker 进程内的运行上下文。

        与 ``request_action``（HTTP 路径，坐席/管理员）共享同一份创建逻辑，
        因此幂等复用与工单版本校验完全一致。
        """
        action = ActionType(action_type)
        self._validate(action, target_assignee_id=None)

        latest = self._requests.find_latest(run_id, action)
        if latest is not None and latest.status is not ActionRequestStatus.PENDING:
            # 这条运行已经走过审批并被拒绝/过期：不能重复申请，也不能继续执行。
            raise ActionRequestNotPending(
                f"该运行此前已提交过 {latest.status.value} 的同一动作申请"
            )

        if latest is not None:
            return {
                "request_id": latest.id,
                "action_type": latest.action_type.value,
                "expires_at": latest.expires_at.isoformat(),
                "replayed": True,
            }

        current = self._tickets.current_version(ticket_id)
        if current is None:
            raise NotFound("工单不存在")

        request = self._requests.add(
            NewActionRequest(
                ticket_id=ticket_id,
                run_id=run_id,
                action_type=action,
                parameters={"reason": reason[:400]},
                ticket_version=current,
            ),
            expires_at=utcnow() + self._ttl,
        )
        return {
            "request_id": request.id,
            "action_type": request.action_type.value,
            "expires_at": request.expires_at.isoformat(),
            "replayed": False,
        }

    # --- 决策 ---------------------------------------------------------------

    def decide(
        self, principal: Principal, request_id: UUID, *, approve: bool
    ) -> ActionDecision:
        """批准或拒绝。

        返回 ``ActionDecision``；「批准但不可执行」与「拒绝」都通过 ``executed`` /
        ``blocked_reason`` 表达，而**过期与已处理**则抛错 —— 它们不是决策结果，
        而是「这次决策根本没生效」。
        """
        self._require_staff(principal)
        now = utcnow()

        request = self._requests.find_by_id(request_id)
        if request is None:
            raise ActionRequestNotFound("操作申请不存在")

        if request.status is not ActionRequestStatus.PENDING:
            raise ActionRequestNotPending(
                f"该申请已是 {request.status.value}，不能重复处理"
            )

        if now >= request.expires_at:
            # **刻意不在这里标记 EXPIRED**：``decide`` 拒绝时不写任何状态。
            # 原因是抛错会让整个事务回滚，标记会连同异常一起消失 —— 那会给人
            # 「已经处理过了」的错觉。状态迁移由 ``expire_due`` 独占负责，
            # 职责因此清晰：decide 只在真正推进状态时写入。
            raise ActionRequestExpired(
                f"申请已于 {request.expires_at.isoformat()} 过期，需要重新发起"
            )

        claimed = self._requests.claim_decision(
            request_id, approved=approve, decided_by=principal.user_id, now=now
        )
        if claimed is None:
            # 条件更新没命中：并发下别人先处理了。
            raise ActionRequestNotPending("该申请已被处理")

        if not approve:
            logger.info("操作申请被拒绝：request_id=%s by=%s", request_id, principal.user_id)
            if self._runs is not None:
                self._runs.hand_back(
                    claimed.run_id, request_id=claimed.id, reason=BLOCKED_REJECTED
                )
            return ActionDecision(
                request=claimed, executed=False, blocked_reason=BLOCKED_REJECTED
            )

        # 批准：执行与记账同事务。执行本身带版本守卫，因此「检查 → 执行」之间的
        # 版本漂移也会被拦下（不依赖这里的读）。
        try:
            result = self._execute(principal, claimed)
        except Exception:
            # 执行失败不能留下「已批准且已记账」的假象：账本尚未写入，
            # 由上层事务回滚；这里只补日志便于定位。
            logger.exception("操作执行失败：request_id=%s", request_id)
            raise

        entry = self._ledger.append(
            action_request_id=claimed.id,
            idempotency_key=self._ledger_key(claimed.id),
            ticket_id=claimed.ticket_id,
            action_type=claimed.action_type,
            result=result,
        )
        logger.info(
            "操作已执行：request_id=%s action=%s ticket=%s",
            request_id,
            claimed.action_type.value,
            claimed.ticket_id,
        )
        if self._runs is not None:
            self._runs.complete_after_action(
                claimed.run_id,
                request_id=claimed.id,
                action_type=claimed.action_type.value,
            )
        return ActionDecision(request=claimed, executed=True, ledger_entry=entry)

    # --- 到期扫描与查询 -----------------------------------------------------

    def expire_due(self, *, limit: int = 100) -> list[ActionRequest]:
        """把到期待审批申请标记为过期。

        由调度器周期调用，是 EXPIRED 状态的**唯一**写入者（``decide`` 拒绝时不写状态，
        见那里的说明）。**不做执行**：过期只让申请失效，不产生任何业务效果。
        """
        now = utcnow()
        expired: list[ActionRequest] = []
        for request in self._requests.list_by_status(
            ActionRequestStatus.PENDING.value, limit=limit
        ):
            if now < request.expires_at:
                continue
            updated = self._requests.mark_expired(request.id, now=now)
            if updated is not None:
                expired.append(updated)
                if self._runs is not None:
                    self._runs.hand_back(
                        updated.run_id, request_id=updated.id, reason="expired"
                    )
        if expired:
            logger.info("已过期 %d 条操作申请", len(expired))
        return expired

    def list_by_run(self, principal: Principal, run_id: UUID) -> list[ActionRequest]:
        self._require_staff(principal)
        return self._requests.list_by_run(run_id)

    def list_pending(self, principal: Principal, *, limit: int = 50) -> list[ActionRequest]:
        self._require_staff(principal)
        return self._requests.list_by_status(ActionRequestStatus.PENDING.value, limit=limit)

    def list_by_status_value(
        self, principal: Principal, status: str, *, limit: int = 50
    ) -> list[ActionRequest]:
        """按状态字符串列出申请。未知状态直接拒绝，避免静默返回空列表。"""
        self._require_staff(principal)
        try:
            parsed = ActionRequestStatus(status)
        except ValueError as exc:
            raise InvalidRequest(f"未知状态：{status}") from exc
        return self._requests.list_by_status(parsed.value, limit=limit)

    def get_request(self, principal: Principal, request_id: UUID) -> ActionRequest:
        self._require_staff(principal)
        request = self._requests.find_by_id(request_id)
        if request is None:
            raise ActionRequestNotFound("操作申请不存在")
        return request

    def find_ledger_entry(self, request_id: UUID) -> ActionLedgerEntry | None:
        """查某条申请的执行记录。账本只读，没有删除接口。"""
        return self._ledger.find_by_request(request_id)

    # --- 内部 ---------------------------------------------------------------

    def _execute(
        self, principal: Principal, request: ActionRequest
    ) -> dict[str, object]:
        """执行已批准的动作，返回写入账本的结果摘要。"""
        if request.action_type is ActionType.CLOSE_TICKET:
            new_version = self._tickets.close_ticket(
                principal,
                ticket_id=request.ticket_id,
                expected_version=request.ticket_version,
            )
            return {
                "action": request.action_type.value,
                "ticket_id": str(request.ticket_id),
                "ticket_version": new_version,
                "status": "CLOSED",
            }

        assignee = request.target_assignee_id
        if assignee is None:  # pragma: no cover - 创建时已强制要求
            raise InvalidRequest("转派申请缺少目标坐席")
        new_version = self._tickets.transfer_ticket(
            principal,
            ticket_id=request.ticket_id,
            assignee_id=assignee,
            expected_version=request.ticket_version,
        )
        return {
            "action": request.action_type.value,
            "ticket_id": str(request.ticket_id),
            "ticket_version": new_version,
            "assignee_id": str(assignee),
        }

    @staticmethod
    def _ledger_key(request_id: UUID) -> str:
        return f"{LEDGER_KEY_PREFIX}:{request_id}"

    @staticmethod
    def _validate(action_type: ActionType, target_assignee_id: UUID | None) -> None:
        if action_type is ActionType.CLOSE_TICKET and target_assignee_id is not None:
            raise InvalidRequest("关闭工单不应带目标坐席")
        if action_type is ActionType.TRANSFER_TICKET and target_assignee_id is None:
            raise InvalidRequest("转派工单必须指定目标坐席")

    @staticmethod
    def _require_staff(principal: Principal) -> None:
        """首版不要求双人审批，但申请与决策都必须由坐席或管理员发起（PLAN §5）。"""
        if not principal.is_staff:
            raise Forbidden("仅坐席与管理员可以发起或审批操作")


def now_iso(moment: datetime) -> str:
    """统一 ISO 8601 输出（AGENTS.md §4：时间使用 UTC ISO 8601）。"""
    return moment.isoformat()
