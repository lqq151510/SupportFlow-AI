"""ticket 模块的 ORM 表。

``version`` 列通过 SQLAlchemy 的 ``version_id_col`` 声明为乐观锁：并发更新会触发
``StaleDataError``，由应用层转换为稳定的冲突错误码，而不是静默覆盖。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Sequence,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from supportflow.shared.clock import utcnow
from supportflow.shared.db import Base
from supportflow.ticket.domain.models import DraftAuthor, DraftStatus, TicketCategory, TicketStatus

TICKET_NO_SEQUENCE = Sequence("ticket_no_seq")

_CATEGORY_SQL = ", ".join(f"'{code}'" for code in TicketCategory)
_STATUS_SQL = ", ".join(f"'{code}'" for code in TicketStatus)


class TicketRow(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint(f"status IN ({_STATUS_SQL})", name="ck_tickets_status"),
        CheckConstraint(
            f"category IS NULL OR category IN ({_CATEGORY_SQL})", name="ck_tickets_category"
        ),
        Index("ix_tickets_submitter_created", "submitter_id", "created_at"),
        Index("ix_tickets_status_assignee_created", "status", "assignee_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    ticket_no: Mapped[str] = mapped_column(String(32), unique=True)
    submitter_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    subject: Mapped[str] = mapped_column(String(200))
    body_raw: Mapped[str] = mapped_column(Text)
    body_cleaned: Mapped[str] = mapped_column(Text)
    clean_version: Mapped[int] = mapped_column(Integer)
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=TicketStatus.OPEN.value)
    assignee_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # SQLAlchemy 声明式要求这是一个放在类体里的普通字典，不能声明为 ClassVar。
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


_DRAFT_STATUS_SQL = ", ".join(f"'{code}'" for code in DraftStatus)
_DRAFT_AUTHOR_SQL = ", ".join(f"'{code}'" for code in DraftAuthor)


class DraftRow(Base):
    __tablename__ = "drafts"
    __table_args__ = (
        CheckConstraint(f"status IN ({_DRAFT_STATUS_SQL})", name="ck_drafts_status"),
        CheckConstraint(f"author IN ({_DRAFT_AUTHOR_SQL})", name="ck_drafts_author"),
        Index("ix_drafts_ticket_version", "ticket_id", "version"),
        Index("ix_drafts_ticket_status", "ticket_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    ticket_id: Mapped[UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    author: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=DraftStatus.ACTIVE.value
    )
    editor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    run_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
