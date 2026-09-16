"""工单模块的领域端口。

仓储签名只接受**原始条件**（提交者 ID、状态、分页），不接收 ``Principal``。
角色判定属于应用层职责，仓储只负责按条件取数 —— 这样端口不必依赖其他模块的领域类型。
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from supportflow.ticket.domain.models import NewTicket, Ticket, TicketCategory, TicketStatus


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
