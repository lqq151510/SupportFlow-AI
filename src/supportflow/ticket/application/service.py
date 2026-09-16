"""工单应用服务。

职责：清洗入库、按角色过滤可见范围、幂等提交、把首次运行的创建委托给
``FirstRunSchedulerPort``。

可见性规则（服务端强制，不依赖前端隐藏）：

* ``AGENT`` / ``ADMIN`` 可见工作区全部工单。
* ``USER`` 只能访问自己提交的工单。
* 访问他人工单返回 ``404 not_found`` 而**不是** 403 —— 避免通过错误码差异探测
  工单是否存在。角色不足（例如非坐席指定 ``model_mode``）才返回 403。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from supportflow.identity.domain.models import Principal
from supportflow.shared.errors import (
    Forbidden,
    ModelModeNotPermitted,
    ModelModeUnavailable,
    NotFound,
    TicketAlreadyClosed,
    TicketVersionChanged,
)
from supportflow.shared.idempotency import ReplayedResponse, fingerprint
from supportflow.ticket.application.ports import FirstRunSchedulerPort, IdempotencyPort
from supportflow.ticket.domain.cleaning import clean_body
from supportflow.ticket.domain.models import NewTicket, Ticket, TicketStatus
from supportflow.ticket.domain.ports import TicketRepositoryPort

SUBMIT_TICKET_SCOPE = "POST /api/v1/tickets"
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@dataclass(frozen=True, slots=True)
class TicketSubmission:
    """提交结果。

    ``payload`` 是**首次提交时落库的响应体**；重放请求原样返回它，因此重放不会
    因为后续代码改动而返回与首次不同的内容 —— 这是幂等语义的一部分。
    """

    ticket_id: UUID
    ticket_no: str
    run_id: UUID
    status_code: int
    replayed: bool
    payload: dict[str, Any]


class TicketService:
    def __init__(
        self,
        tickets: TicketRepositoryPort,
        idempotency: IdempotencyPort,
        scheduler: FirstRunSchedulerPort,
        *,
        default_model_mode: str,
        available_model_modes: frozenset[str],
    ) -> None:
        self._tickets = tickets
        self._idempotency = idempotency
        self._scheduler = scheduler
        self._default_model_mode = default_model_mode
        self._available_model_modes = available_model_modes

    # --- 提交 ---------------------------------------------------------------
    def submit(
        self,
        principal: Principal,
        *,
        subject: str,
        body: str,
        idempotency_key: str,
        model_mode: str | None = None,
    ) -> TicketSubmission:
        requested_mode = model_mode or self._default_model_mode
        if model_mode is not None:
            if not principal.is_staff:
                raise ModelModeNotPermitted("仅坐席与管理员可以按次指定运行模式")
            if requested_mode not in self._available_model_modes:
                # 不降级：记成 real 却由 Mock 执行会让评测数据失真。
                raise ModelModeUnavailable(
                    f"当前构建只提供 {'、'.join(sorted(self._available_model_modes))} 模式"
                )

        request_hash = fingerprint(
            {"subject": subject, "body": body, "model_mode": requested_mode}
        )
        replayed = self._idempotency.reserve(SUBMIT_TICKET_SCOPE, idempotency_key, request_hash)
        if replayed is not None:
            return self._as_replay(replayed)

        cleaned = clean_body(body)
        ticket = self._tickets.add(
            NewTicket(
                submitter_id=principal.user_id,
                subject=subject,
                body_raw=body,
                body_cleaned=cleaned.text,
                clean_version=cleaned.version,
            )
        )
        run_id = self._scheduler.schedule_first_run(
            ticket_id=ticket.id, model_mode=requested_mode
        )

        body_out: dict[str, Any] = {
            "ticket_id": str(ticket.id),
            "ticket_no": ticket.ticket_no,
            "run_id": str(run_id),
            "status": "QUEUED",
            "model_mode": requested_mode,
        }
        self._idempotency.complete(
            SUBMIT_TICKET_SCOPE, idempotency_key, status_code=202, body=body_out
        )
        return TicketSubmission(
            ticket_id=ticket.id,
            ticket_no=ticket.ticket_no,
            run_id=run_id,
            status_code=202,
            replayed=False,
            payload=body_out,
        )

    # --- 查询 ---------------------------------------------------------------
    @staticmethod
    def _require_staff(principal: Principal) -> None:
        """关闭与转派只允许坐席与管理员 —— 且**必须**经审批闭环调用。"""
        if not principal.is_staff:
            raise Forbidden("仅坐席与管理员可以执行该操作")

    def current_version(self, ticket_id: UUID) -> int | None:
        """取工单当前版本。审批模块据此比对「授权时看到的版本」是否仍然成立。"""
        ticket = self._tickets.find_by_id(ticket_id)
        return ticket.version if ticket else None

    def close_ticket(
        self, principal: Principal, ticket_id: UUID, *, expected_version: int
    ) -> int:
        """关闭工单（终态）。仅坐席与管理员可执行，且**必须**通过审批闭环调用。"""
        self._require_staff(principal)
        ticket = self._tickets.find_by_id(ticket_id)
        if ticket is None:
            raise NotFound("工单不存在")
        if ticket.status is TicketStatus.CLOSED:
            raise TicketAlreadyClosed("工单已关闭，不能重复关闭")
        new_version = self._tickets.close(ticket_id, expected_version=expected_version)
        if new_version is None:
            raise TicketVersionChanged(
                f"工单版本已变化（期望 {expected_version}），请重新发起申请"
            )
        return new_version

    def transfer_ticket(
        self,
        principal: Principal,
        ticket_id: UUID,
        *,
        assignee_id: UUID,
        expected_version: int,
    ) -> int:
        """转派工单。仅坐席与管理员可执行，且**必须**通过审批闭环调用。"""
        self._require_staff(principal)
        ticket = self._tickets.find_by_id(ticket_id)
        if ticket is None:
            raise NotFound("工单不存在")
        new_version = self._tickets.transfer(
            ticket_id, assignee_id=assignee_id, expected_version=expected_version
        )
        if new_version is None:
            raise TicketVersionChanged(
                f"工单版本已变化（期望 {expected_version}），请重新发起申请"
            )
        return new_version

    def list_tickets(
        self,
        principal: Principal,
        *,
        status: TicketStatus | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> tuple[list[Ticket], int]:
        scope_submitter = None if principal.is_staff else principal.user_id
        bounded_limit = max(1, min(limit, MAX_PAGE_SIZE))
        items = self._tickets.list_tickets(
            submitter_id=scope_submitter, status=status, limit=bounded_limit, offset=max(0, offset)
        )
        total = self._tickets.count_tickets(submitter_id=scope_submitter, status=status)
        return items, total

    def get_ticket(self, principal: Principal, ticket_id: UUID) -> Ticket:
        ticket = self._tickets.find_by_id(ticket_id)
        if ticket is None:
            raise NotFound("工单不存在")
        if not principal.is_staff and ticket.submitter_id != principal.user_id:
            # 刻意返回 404：不泄露他人工单是否存在。
            raise NotFound("工单不存在")
        return ticket

    @staticmethod
    def _as_replay(replayed: ReplayedResponse) -> TicketSubmission:
        payload = replayed.body
        return TicketSubmission(
            ticket_id=UUID(str(payload["ticket_id"])),
            ticket_no=str(payload["ticket_no"]),
            run_id=UUID(str(payload["run_id"])),
            status_code=replayed.status_code,
            replayed=True,
            payload=dict(payload),
        )
