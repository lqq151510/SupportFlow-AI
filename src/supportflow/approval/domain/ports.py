"""审批域的端口。

两个幂等边界都在仓储层表达，因此**由数据库而不是应用层保证**：

1. ``action_requests`` 上「同一运行 + 同一动作类型至多一个待审批申请」的部分唯一索引；
2. ``action_ledger`` 上 ``action_request_id`` 与 ``idempotency_key`` 两个唯一约束。

应用层的「先查后写」只是优化，不是保证 —— 并发下会漏。
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from supportflow.approval.domain.models import (
    ActionLedgerEntry,
    ActionRequest,
    ActionType,
    NewActionRequest,
)
from supportflow.identity.domain.models import Principal


class ActionRequestRepositoryPort(Protocol):
    def add(self, request: NewActionRequest, *, expires_at: datetime) -> ActionRequest: ...

    def find_by_id(self, request_id: UUID) -> ActionRequest | None: ...

    def find_latest(self, run_id: UUID, action_type: ActionType) -> ActionRequest | None:
        """查同一运行下该动作类型的**最近一条**申请（含已处理）。

        用于识别「这条运行已经走过审批」—— 否则重放会创建第二条申请。
        """
        ...

    def find_pending(self, run_id: UUID, action_type: ActionType) -> ActionRequest | None:
        """查同一运行下该动作类型的待审批申请 —— 用于幂等重放。"""
        ...

    def list_by_run(self, run_id: UUID) -> list[ActionRequest]: ...

    def list_by_status(
        self, status: str, *, limit: int = 50
    ) -> list[ActionRequest]: ...

    def claim_decision(
        self, request_id: UUID, *, approved: bool, decided_by: UUID, now: datetime
    ) -> ActionRequest | None:
        """**原子地**把 PENDING 迁移到 APPROVED/REJECTED。

        返回 ``None`` 表示状态已不是 PENDING（别人先处理了，或已过期）。
        用条件更新而不是「先读后写」，是为了让并发双审在数据库层面被拦下。
        """
        ...

    def mark_expired(self, request_id: UUID, *, now: datetime) -> ActionRequest | None: ...


class ActionLedgerPort(Protocol):
    def append(
        self,
        *,
        action_request_id: UUID,
        idempotency_key: str,
        ticket_id: UUID,
        action_type: ActionType,
        result: dict[str, object],
    ) -> ActionLedgerEntry:
        """追加一条执行记录。

        ``action_request_id`` / ``idempotency_key`` 均有唯一约束：重复执行会在这里
        直接失败，而不是产生第二条业务效果。
        """
        ...

    def find_by_request(self, action_request_id: UUID) -> ActionLedgerEntry | None: ...


class TicketActionPort(Protocol):
    """审批执行需要的最小工单能力。

    工单表的读写全部经由这个端口（由组合根适配 ticket 模块的 application 服务），
    因此审批模块**不直接触碰工单表** —— 这是 AGENTS.md §3 的模块边界要求。

    刻意只暴露两个动作 + 一个版本读取，而不是把整个工单服务注进来 ——
    审批模块不该有能力做关闭/转派以外的事（AGENTS.md §3）。
    """

    def current_version(self, ticket_id: UUID) -> int | None: ...

    def close_ticket(
        self, principal: Principal, *, ticket_id: UUID, expected_version: int
    ) -> int:
        """关闭工单并返回新版本。

        ``principal`` 是**审批人**：授权判定留在工单模块，审批模块不自行放行。
        版本不符时抛 ``TicketVersionChanged``。
        """
        ...

    def transfer_ticket(
        self,
        principal: Principal,
        *,
        ticket_id: UUID,
        assignee_id: UUID,
        expected_version: int,
    ) -> int:
        """转派并返回新版本。"""
        ...


class RunOutcomePort(Protocol):
    """把审批结果推进到**运行**的终态。

    刻意做成端口并由组合根实现：审批模块因此不认识 agent 模块，
    依赖方向保持单向（approval ← bootstrap → agent）。

    实现**必须幂等**：只有运行仍处于 ``WAITING_APPROVAL`` 时才迁移，
    重复调用（任务重投、检查点重放）不产生第二笔效果。
    """

    def complete_after_action(
        self, run_id: UUID, *, request_id: UUID, action_type: str
    ) -> None:
        """动作已执行并记账 → 运行 COMPLETED。"""
        ...

    def hand_back(self, run_id: UUID, *, request_id: UUID, reason: str) -> None:
        """拒绝 / 过期 → 运行 NEEDS_HUMAN，由人工决定下一步。"""
        ...
