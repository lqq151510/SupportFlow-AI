"""初始 schema · 阶段 2 基础闭环

Revision ID: 0001
Revises:
Create Date: 2026-09-11

覆盖阶段 2 实际用到的 8 张表：身份（users / user_sessions）、工单（tickets）、
运行（agent_runs / run_events / run_steps）、共享（audit_logs /
idempotency_records）。知识库、审批与评测相关表在后续阶段随功能引入，不在此处
预留空表 —— 空表无法验证约束是否正确，只会积累猜测。

两处需要特别说明：

* ``run_events`` 是**按 ``created_at`` 月分区**的表。分区表的唯一约束必须包含
  分区键，因此主键是 ``(id, created_at)``，而事件顺序由全局单调的 ``id`` 保证。
  本迁移额外为当月与未来两个月建好分区，使空库 ``upgrade head`` 之后即可直接
  写入；后续月份由应用启动时的 ``ensure_run_event_partitions`` 补齐。
* ``agent_runs`` 上有一个**部分唯一索引**，保证同一工单同时只有一个活动运行。
  它的判定条件必须与 ``supportflow.agent.domain.models.ACTIVE_RUN_STATUSES``
  严格一致，改状态机时要同时改这里。
"""

from __future__ import annotations

import calendar
import datetime
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TICKET_CATEGORIES = (
    "DELIVERY",
    "RETURN_POLICY",
    "PRODUCT_USAGE",
    "ACCOUNT",
    "COMPLAINT",
    "OTHER",
)
RUN_STATUSES = ("QUEUED", "RUNNING", "WAITING_APPROVAL", "COMPLETED", "NEEDS_HUMAN", "FAILED")
ACTIVE_RUN_STATUSES = ("QUEUED", "RUNNING", "WAITING_APPROVAL")
RUN_EVENT_TYPES = (
    "run.started",
    "run.step.started",
    "run.step.completed",
    "retrieval.completed",
    "tool.requested",
    "tool.completed",
    "draft.created",
    "citation.invalid",
    "approval.required",
    "action.executed",
    "run.needs_human",
    "run.completed",
    "run.failed",
)


def _sql(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _month_starts(year: int, month: int, count: int) -> list[tuple[int, int]]:
    months: list[tuple[int, int]] = []
    index = year * 12 + (month - 1)
    for offset in range(count):
        absolute = index + offset
        months.append((absolute // 12, absolute % 12 + 1))
    return months


def _create_run_event_partitions() -> None:
    """为当月及未来两个月预建分区（``IF NOT EXISTS``，可安全重跑）。

    分区边界由**执行迁移时的系统日期**推导，而不是写死常量：这样空库
    ``upgrade head`` 之后立即可写；更远的月份由应用启动时的
    ``ensure_run_event_partitions`` 补齐。
    """
    today = datetime.datetime.now(datetime.UTC).date()
    bind = op.get_bind()
    for year, month in _month_starts(today.year, today.month, 3):
        start = datetime.date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end = start.replace(day=last_day) + datetime.timedelta(days=1)
        bind.execute(
            sa.text(
                f"CREATE TABLE IF NOT EXISTS run_events_{year:04d}{month:02d} "
                f"PARTITION OF run_events FOR VALUES "
                f"FROM ('{start.isoformat()}') TO ('{end.isoformat()}')"
            )
        )


def upgrade() -> None:
    # --- 序列 ---------------------------------------------------------------
    op.execute("CREATE SEQUENCE IF NOT EXISTS ticket_no_seq")
    op.execute("CREATE SEQUENCE IF NOT EXISTS run_events_id_seq")

    # --- 身份 ---------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('USER', 'AGENT', 'ADMIN')", name="ck_users_role"),
        sa.CheckConstraint("status IN ('ACTIVE', 'DISABLED')", name="ck_users_status"),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_role_status", "users", ["role", "status"])

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=400), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_sessions_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_sessions"),
        sa.UniqueConstraint("token_hash", name="uq_user_sessions_token_hash"),
    )
    op.create_index(
        "ix_user_sessions_user_expires", "user_sessions", ["user_id", "expires_at"]
    )

    # --- 工单 ---------------------------------------------------------------
    op.create_table(
        "tickets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticket_no", sa.String(length=32), nullable=False),
        sa.Column("submitter_id", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("body_raw", sa.Text(), nullable=False),
        sa.Column("body_cleaned", sa.Text(), nullable=False),
        sa.Column("clean_version", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("assignee_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('OPEN', 'CLOSED')", name="ck_tickets_status"),
        sa.CheckConstraint(
            f"category IS NULL OR category IN ({_sql(TICKET_CATEGORIES)})",
            name="ck_tickets_category",
        ),
        sa.ForeignKeyConstraint(
            ["submitter_id"],
            ["users.id"],
            name="fk_tickets_submitter_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assignee_id"],
            ["users.id"],
            name="fk_tickets_assignee_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tickets"),
        sa.UniqueConstraint("ticket_no", name="uq_tickets_ticket_no"),
    )
    op.create_index("ix_tickets_submitter_created", "tickets", ["submitter_id", "created_at"])
    op.create_index(
        "ix_tickets_status_assignee_created",
        "tickets",
        ["status", "assignee_id", "created_at"],
    )

    # --- 运行 ---------------------------------------------------------------
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("model_mode", sa.String(length=8), nullable=False),
        sa.Column("chat_model_name", sa.String(length=120), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("step_count", sa.Integer(), nullable=False),
        sa.Column("tool_call_count", sa.Integer(), nullable=False),
        sa.Column("lease_owner", sa.String(length=120), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_of_run_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(f"status IN ({_sql(RUN_STATUSES)})", name="ck_agent_runs_status"),
        sa.CheckConstraint("model_mode IN ('mock', 'real')", name="ck_agent_runs_model_mode"),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["tickets.id"],
            name="fk_agent_runs_ticket_id_tickets",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["retry_of_run_id"],
            ["agent_runs.id"],
            name="fk_agent_runs_retry_of_run_id_agent_runs",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agent_runs"),
    )
    # 同一工单同时只允许一个活动运行 —— 应用层不做「先查后写」判重。
    op.create_index(
        "uq_agent_runs_active_per_ticket",
        "agent_runs",
        ["ticket_id"],
        unique=True,
        postgresql_where=sa.text(f"status IN ({_sql(ACTIVE_RUN_STATUSES)})"),
    )
    op.create_index("ix_agent_runs_status_lease", "agent_runs", ["status", "lease_expires_at"])
    op.create_index("ix_agent_runs_ticket_created", "agent_runs", ["ticket_id", "created_at"])

    op.create_table(
        "run_events",
        sa.Column(
            "id",
            sa.BigInteger(),
            server_default=sa.text("nextval('run_events_id_seq')"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(f"event_type IN ({_sql(RUN_EVENT_TYPES)})", name="ck_run_events_type"),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["agent_runs.id"],
            name="fk_run_events_run_id_agent_runs",
            ondelete="CASCADE",
        ),
        # 分区表的唯一约束必须包含分区键，因此主键是 (id, created_at)。
        sa.PrimaryKeyConstraint("id", "created_at", name="pk_run_events"),
        postgresql_partition_by="RANGE (created_at)",
    )
    op.create_index("ix_run_events_run_id", "run_events", ["run_id", "id"])
    _create_run_event_partitions()

    op.create_table(
        "run_steps",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("step_no", sa.Integer(), nullable=False),
        sa.Column("node_name", sa.String(length=64), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["agent_runs.id"],
            name="fk_run_steps_run_id_agent_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("run_id", "step_no", name="pk_run_steps"),
    )

    # --- 共享 ---------------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=400), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        # 刻意不建 actor_id 外键：审计记录必须比用户活得更久。
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
    )
    op.create_index("ix_audit_logs_actor_created", "audit_logs", ["actor_id", "created_at"])
    op.create_index(
        "ix_audit_logs_resource", "audit_logs", ["resource_type", "resource_id", "created_at"]
    )

    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("key", sa.String(length=200), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        # 并发安全由此约束保证，而不是应用层「先查后写」。
        sa.PrimaryKeyConstraint("id", name="pk_idempotency_records"),
        sa.UniqueConstraint("scope", "key", name="uq_idempotency_scope_key"),
    )
    op.create_index("ix_idempotency_records_expires_at", "idempotency_records", ["expires_at"])


def downgrade() -> None:
    op.drop_table("idempotency_records")
    op.drop_table("audit_logs")
    op.drop_table("run_steps")
    # 分区随父表一起删除。
    op.drop_table("run_events")
    op.drop_table("agent_runs")
    op.drop_table("tickets")
    op.drop_table("user_sessions")
    op.drop_table("users")
    op.execute("DROP SEQUENCE IF EXISTS run_events_id_seq")
    op.execute("DROP SEQUENCE IF EXISTS ticket_no_seq")
