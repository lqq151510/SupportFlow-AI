"""审批模块 ORM 表（PLAN 表 #15 `action_requests`、#16 `action_ledger`）。

两条不变量由**数据库**保证，而不是应用层：

1. ``uq_action_requests_pending_per_run``：同一运行 + 同一动作类型至多一个待审批申请。
   部分唯一索引（``WHERE status = 'PENDING'``）—— 已处理的申请不占位，因此同一次运行
   可以先被拒绝、再重新申请。
2. ``action_ledger`` 上 ``action_request_id`` 与 ``idempotency_key`` 两个唯一约束 ——
   PLAN 明确写「两个唯一约束即幂等边界」。重复审批、任务重投或检查点重放都会撞上它。

``action_ledger`` 只追加，不提供删除接口（AGENTS.md §7）。
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
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from supportflow.approval.domain.models import ActionRequestStatus, ActionType
from supportflow.shared.clock import utcnow
from supportflow.shared.db import Base

_ACTION_SQL = ", ".join(f"'{value.value}'" for value in ActionType)
_STATUS_SQL = ", ".join(f"'{value.value}'" for value in ActionRequestStatus)


class ActionRequestRow(Base):
    __tablename__ = "action_requests"
    __table_args__ = (
        CheckConstraint(f"action_type IN ({_ACTION_SQL})", name="ck_action_requests_action_type"),
        CheckConstraint(f"status IN ({_STATUS_SQL})", name="ck_action_requests_status"),
        CheckConstraint("ticket_version > 0", name="ck_action_requests_ticket_version"),
        # 同一运行的同一动作类型至多一个待审批申请。
        Index(
            "uq_action_requests_pending_per_run",
            "run_id",
            "action_type",
            unique=True,
            postgresql_where=text("status = 'PENDING'"),
        ),
        # PLAN 表 #15 指定的两条访问路径：
        # 到期扫描（status, expires_at）与按工单回溯（ticket_id, created_at）。
        Index("ix_action_requests_status_expires", "status", "expires_at"),
        Index("ix_action_requests_ticket_created", "ticket_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    ticket_id: Mapped[UUID] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"))
    run_id: Mapped[UUID] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"))
    action_type: Mapped[str] = mapped_column(String(32))
    #: **不可变**的动作参数：审批针对的就是它，改它等于换了一个请求。
    parameters_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    #: 发起申请时的工单版本。版本一变，授权前提即不成立（PLAN §5）。
    ticket_version: Mapped[int] = mapped_column(Integer)
    #: 转派目标。PLAN 表 #15 把它单列，而不是只塞在 parameters_json 里 ——
    #: 于是「谁被指派」可以被直接查询与外键约束，不必解析 JSON。
    target_assignee_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), default=ActionRequestStatus.PENDING.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ActionLedgerRow(Base):
    __tablename__ = "action_ledger"
    __table_args__ = (
        CheckConstraint(f"action_type IN ({_ACTION_SQL})", name="ck_action_ledger_action_type"),
        Index("ix_action_ledger_ticket_executed", "ticket_id", "executed_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    #: 唯一约束 1：同一申请只能产生一条业务效果。
    action_request_id: Mapped[UUID] = mapped_column(
        ForeignKey("action_requests.id", ondelete="RESTRICT"), unique=True
    )
    #: 唯一约束 2：跨重投/重放的幂等键。
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    ticket_id: Mapped[UUID] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"))
    action_type: Mapped[str] = mapped_column(String(32))
    result_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
