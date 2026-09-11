"""agent 模块的 ORM 表。

两个关键设计：

1. **运行互斥**由 ``agent_runs`` 上的**部分唯一索引**保证，条件与
   ``ACTIVE_RUN_STATUSES`` 严格一致 —— 应用层不做「先查后写」判重。
2. ``run_events`` 是**按 ``created_at`` 月分区的表**。注意分区表的唯一约束必须
   包含分区键，因此主键为 ``(id, created_at)``，且没有 ``(run_id, seq)`` 全局唯一
   约束：同一次运行的事件落在同一个月分区内，其顺序由全局单调的 ``id`` 保证。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Sequence,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from supportflow.agent.domain.models import ACTIVE_RUN_STATUSES, RunEventType, RunStatus
from supportflow.shared.clock import utcnow
from supportflow.shared.db import Base

RUN_EVENT_ID_SEQUENCE = Sequence("run_events_id_seq")

_RUN_STATUS_SQL = ", ".join(f"'{status.value}'" for status in RunStatus)
_ACTIVE_STATUS_SQL = ", ".join(f"'{status.value}'" for status in ACTIVE_RUN_STATUSES)
_EVENT_TYPE_SQL = ", ".join(f"'{event.value}'" for event in RunEventType)
_MODEL_MODE_SQL = "'mock', 'real'"


class AgentRunRow(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint(f"status IN ({_RUN_STATUS_SQL})", name="ck_agent_runs_status"),
        CheckConstraint(f"model_mode IN ({_MODEL_MODE_SQL})", name="ck_agent_runs_model_mode"),
        Index(
            "uq_agent_runs_active_per_ticket",
            "ticket_id",
            unique=True,
            postgresql_where=text(f"status IN ({_ACTIVE_STATUS_SQL})"),
        ),
        Index("ix_agent_runs_status_lease", "status", "lease_expires_at"),
        Index("ix_agent_runs_ticket_created", "ticket_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    ticket_id: Mapped[UUID] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default=RunStatus.QUEUED.value)
    model_mode: Mapped[str] = mapped_column(String(8), default="mock")
    chat_model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    step_count: Mapped[int] = mapped_column(Integer, default=0)
    tool_call_count: Mapped[int] = mapped_column(Integer, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    retry_of_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RunEventRow(Base):
    """按月分区的运行事件表。

    ``payload`` 只允许存脱敏后的结构化信息；禁止写入客户原文或密钥。
    """

    __tablename__ = "run_events"
    __table_args__ = (
        CheckConstraint(f"event_type IN ({_EVENT_TYPE_SQL})", name="ck_run_events_type"),
        Index("ix_run_events_run_id", "run_id", "id"),
        {"postgresql_partition_by": "RANGE (created_at)"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        RUN_EVENT_ID_SEQUENCE,
        primary_key=True,
        autoincrement=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, default=utcnow
    )
    run_id: Mapped[UUID] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)


class RunStepRow(Base):
    __tablename__ = "run_steps"

    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), primary_key=True
    )
    step_no: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_name: Mapped[str] = mapped_column(String(64))
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


__all__ = [
    "RUN_EVENT_ID_SEQUENCE",
    "AgentRunRow",
    "RunEventRow",
    "RunStepRow",
]
