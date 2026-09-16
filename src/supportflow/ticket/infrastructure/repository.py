"""工单模块的持久化实现。"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select, update
from sqlalchemy.orm import Session

from supportflow.shared.clock import utcnow
from supportflow.ticket.domain.models import (
    Draft,
    DraftAuthor,
    DraftStatus,
    NewTicket,
    Ticket,
    TicketCategory,
    TicketStatus,
)
from supportflow.ticket.infrastructure.tables import (
    TICKET_NO_SEQUENCE,
    DraftRow,
    TicketRow,
)


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

    def close(self, ticket_id: UUID, *, expected_version: int) -> int | None:
        """条件更新：``WHERE version = :expected AND status = 'OPEN'``。

        返回新版本；受影响行数为 0 表示版本不符（或工单已关闭），由用例层区分。
        """
        return self._apply_action(
            ticket_id,
            expected_version=expected_version,
            values={"status": TicketStatus.CLOSED.value},
            require_open=True,
        )

    def transfer(
        self, ticket_id: UUID, *, assignee_id: UUID, expected_version: int
    ) -> int | None:
        return self._apply_action(
            ticket_id,
            expected_version=expected_version,
            values={"assignee_id": assignee_id},
            require_open=False,
        )

    def _apply_action(
        self,
        ticket_id: UUID,
        *,
        expected_version: int,
        values: dict[str, object],
        require_open: bool,
    ) -> int | None:
        conditions = [
            TicketRow.id == ticket_id,
            TicketRow.version == expected_version,
        ]
        if require_open:
            conditions.append(TicketRow.status == TicketStatus.OPEN.value)
        row = self._session.execute(
            update(TicketRow)
            .where(*conditions)
            .values(version=TicketRow.version + 1, updated_at=utcnow(), **values)
            .returning(TicketRow.version)
        ).one_or_none()
        return int(row[0]) if row is not None else None

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


def _to_draft(row: DraftRow) -> Draft:
    return Draft(
        id=row.id,
        ticket_id=row.ticket_id,
        version=row.version,
        author=DraftAuthor(row.author),
        content=row.content,
        citations=[dict(item) for item in row.citations] if row.citations else [],
        status=DraftStatus(row.status),
        editor_user_id=row.editor_user_id,
        run_id=row.run_id,
        created_at=row.created_at,
        published_at=row.published_at,
        published_by=row.published_by,
    )


class SqlAlchemyDraftRepository:
    """草稿版本仓储。同一事务内新增版本会把旧 ACTIVE 版本归档。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _next_version(self, ticket_id: UUID) -> int:
        current = self._session.scalar(
            select(func.coalesce(func.max(DraftRow.version), 0)).where(
                DraftRow.ticket_id == ticket_id
            )
        )
        return int(current or 0) + 1

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
        # 同一事务内把当前 ACTIVE 版本归档，避免两张 ACTIVE 并存。
        self._session.execute(
            update(DraftRow)
            .where(DraftRow.ticket_id == ticket_id, DraftRow.status == DraftStatus.ACTIVE.value)
            .values(status=DraftStatus.ARCHIVED.value, updated_at=utcnow())
        )
        row = DraftRow(
            ticket_id=ticket_id,
            version=self._next_version(ticket_id),
            author=author.value,
            content=content,
            citations=citations,
            status=DraftStatus.ACTIVE.value,
            editor_user_id=editor_user_id,
            run_id=run_id,
        )
        self._session.add(row)
        self._session.flush()
        return _to_draft(row)

    def find_by_id(self, draft_id: UUID) -> Draft | None:
        row = self._session.get(DraftRow, draft_id)
        return _to_draft(row) if row else None

    def find_active(self, ticket_id: UUID) -> Draft | None:
        row = self._session.scalar(
            select(DraftRow)
            .where(DraftRow.ticket_id == ticket_id, DraftRow.status == DraftStatus.ACTIVE.value)
            .order_by(DraftRow.version.desc())
        )
        return _to_draft(row) if row else None

    def list_for_ticket(self, ticket_id: UUID) -> list[Draft]:
        rows = self._session.scalars(
            select(DraftRow)
            .where(DraftRow.ticket_id == ticket_id)
            .order_by(DraftRow.version.asc())
        ).all()
        return [_to_draft(row) for row in rows]

    def publish(self, draft_id: UUID, *, published_by: UUID) -> Draft | None:
        # 条件更新：只有 ACTIVE 的草稿能被发布；并发发布只有第一个成功。
        now = utcnow()
        result = self._session.execute(
            update(DraftRow)
            .where(DraftRow.id == draft_id, DraftRow.status == DraftStatus.ACTIVE.value)
            .values(
                status=DraftStatus.PUBLISHED.value,
                published_at=now,
                published_by=published_by,
                updated_at=now,
            )
            .returning(DraftRow.id)
        )
        if result.one_or_none() is None:
            return None
        return self.find_by_id(draft_id)
