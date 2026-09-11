"""工单模块的持久化实现。"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from supportflow.shared.clock import utcnow
from supportflow.ticket.domain.models import (
    NewTicket,
    Ticket,
    TicketCategory,
    TicketStatus,
)
from supportflow.ticket.infrastructure.tables import TICKET_NO_SEQUENCE, TicketRow


def _to_ticket(row: TicketRow) -> Ticket:
    return Ticket(
        id=row.id,
        ticket_no=row.ticket_no,
        submitter_id=row.submitter_id,
        subject=row.subject,
        body_raw=row.body_raw,
        body_cleaned=row.body_cleaned,
        clean_version=row.clean_version,
        category=TicketCategory(row.category) if row.category else None,
        status=TicketStatus(row.status),
        assignee_id=row.assignee_id,
        version=row.version,
        created_at=row.created_at,
        closed_at=row.closed_at,
    )


class SqlAlchemyTicketRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, new_ticket: NewTicket) -> Ticket:
        serial = self._session.scalar(select(TICKET_NO_SEQUENCE.next_value()))
        now = utcnow()
        row = TicketRow(
            ticket_no=f"T-{now:%Y%m%d}-{int(serial or 0):05d}",
            submitter_id=new_ticket.submitter_id,
            subject=new_ticket.subject,
            body_raw=new_ticket.body_raw,
            body_cleaned=new_ticket.body_cleaned,
            clean_version=new_ticket.clean_version,
            status=TicketStatus.OPEN.value,
        )
        self._session.add(row)
        self._session.flush()
        return _to_ticket(row)

    def find_by_id(self, ticket_id: UUID) -> Ticket | None:
        row = self._session.get(TicketRow, ticket_id)
        return _to_ticket(row) if row else None

    def list_tickets(
        self,
        *,
        submitter_id: UUID | None,
        status: TicketStatus | None,
        limit: int,
        offset: int,
    ) -> list[Ticket]:
        stmt = select(TicketRow).order_by(TicketRow.created_at.desc(), TicketRow.id)
        stmt = self._apply_filters(stmt, submitter_id=submitter_id, status=status)
        rows = self._session.scalars(stmt.limit(limit).offset(offset)).all()
        return [_to_ticket(row) for row in rows]

    def count_tickets(
        self, *, submitter_id: UUID | None, status: TicketStatus | None
    ) -> int:
        stmt = select(func.count(TicketRow.id))
        stmt = self._apply_filters(stmt, submitter_id=submitter_id, status=status)
        return int(self._session.scalar(stmt) or 0)

    def assign_category(self, ticket_id: UUID, category: TicketCategory) -> None:
        row = self._session.get(TicketRow, ticket_id)
        if row is None:
            return
        row.category = category.value

    @staticmethod
    def _apply_filters(
        stmt: Select[Any],
        *,
        submitter_id: UUID | None,
        status: TicketStatus | None,
    ) -> Select[Any]:
        if submitter_id is not None:
            stmt = stmt.where(TicketRow.submitter_id == submitter_id)
        if status is not None:
            stmt = stmt.where(TicketRow.status == status.value)
        return stmt
