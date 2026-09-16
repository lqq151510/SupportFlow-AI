"""工单模块的领域端口。

仓储签名只接受**原始条件**（提交者 ID、状态、分页），不接收 ``Principal``。
角色判定属于应用层职责，仓储只负责按条件取数 —— 这样端口不必依赖其他模块的领域类型。
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from supportflow.ticket.domain.models import (
    Draft,
    DraftAuthor,
    NewTicket,
    Ticket,
    TicketCategory,
    TicketStatus,
)


class TicketRepositoryPort(Protocol):
    def add(self, new_ticket: NewTicket) -> Ticket: ...

    def find_by_id(self, ticket_id: UUID) -> Ticket | None: ...

    def list_tickets(
        self,
        *,
        submitter_id: UUID | None,
        status: TicketStatus | None,
        limit: int,
        offset: int,
    ) -> list[Ticket]: ...

    def count_tickets(
        self, *, submitter_id: UUID | None, status: TicketStatus | None
    ) -> int: ...

    def assign_category(self, ticket_id: UUID, category: TicketCategory) -> None: ...

    def close(self, ticket_id: UUID, *, expected_version: int) -> int | None:
        """按乐观锁关闭工单，返回新版本；版本不符返回 ``None``。

        条件更新（``WHERE version = :expected AND status = 'OPEN'``）是**唯一**的并发保证，
        不能用「先读后写」替代。
        """
        ...

    def transfer(
        self, ticket_id: UUID, *, assignee_id: UUID, expected_version: int
    ) -> int | None:
        """按乐观锁转派工单，返回新版本；版本不符返回 ``None``。"""
        ...


class DraftRepositoryPort(Protocol):
    """草稿版本仓储。按工单维度维护 ACTIVE/PUBLISHED/ARCHIVED 版本链。"""

    def add_new_version(
        self,
        ticket_id: UUID,
        *,
        author: DraftAuthor,
        content: str,
        citations: list[dict[str, Any]],
        run_id: UUID | None,
        editor_user_id: UUID | None,
    ) -> Draft:
        """新增一个 ACTIVE 版本，并把此前 ACTIVE 的版本置为 ARCHIVED。

        返回新建的版本；版本号按工单内单调递增。
        """
        ...

    def find_by_id(self, draft_id: UUID) -> Draft | None: ...

    def find_active(self, ticket_id: UUID) -> Draft | None: ...

    def list_for_ticket(self, ticket_id: UUID) -> list[Draft]: ...

    def publish(self, draft_id: UUID, *, published_by: UUID) -> Draft | None:
        """把 ACTIVE 草稿发布为正式回复。仅 ACTIVE 可发布；返回发布后的草稿。

        并发发布时只有第一个成功（条件更新 ``WHERE status = 'ACTIVE'``），
        其余返回 ``None`` —— 这是「至多一次发布」的保证，不靠「先查后写」。
        """
        ...
