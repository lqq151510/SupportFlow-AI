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
