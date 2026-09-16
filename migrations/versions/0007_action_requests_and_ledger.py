"""操作申请与执行账本（PLAN 表 #15、#16）。

不变量由数据库保证：

- 同一运行 + 同一动作类型至多一个待审批申请（部分唯一索引）；
- 账本的 ``action_request_id`` 与 ``idempotency_key`` 各有唯一约束，
  即 PLAN 所说的「两个唯一约束即幂等边界」。

因此这里不写「先查后写」判重：并发下它会漏，而且真正的保证在数据库上。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "action_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("action_type", sa.String(32), nullable=False),
        sa.Column("parameters_json", postgresql_jsonb(), nullable=False),
        sa.Column("ticket_version", sa.Integer(), nullable=False),
        sa.Column("target_assignee_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id", name="pk_action_requests"),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["tickets.id"], name="fk_action_requests_ticket_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["agent_runs.id"], name="fk_action_requests_run_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"], ["users.id"], name="fk_action_requests_decided_by", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["target_assignee_id"],
            ["users.id"],
            name="fk_action_requests_target_assignee_id",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "action_type IN ('CLOSE_TICKET', 'TRANSFER_TICKET')",
            name="ck_action_requests_action_type",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED')",
            name="ck_action_requests_status",
        ),
        sa.CheckConstraint("ticket_version > 0", name="ck_action_requests_ticket_version"),
    )
    # 同一运行的同一动作类型至多一个待审批申请：已处理的申请不占位，
    # 因此「先被拒绝、再重新申请」是允许的。
    op.create_index(
        "uq_action_requests_pending_per_run",
        "action_requests",
        ["run_id", "action_type"],
        unique=True,
        postgresql_where=sa.text("status = 'PENDING'"),
    )
    # 到期扫描的访问路径。
    op.create_index("ix_action_requests_status_expires", "action_requests", ["status", "expires_at"])
    op.create_index(
        "ix_action_requests_ticket_created", "action_requests", ["ticket_id", "created_at"]
    )

    op.create_table(
        "action_ledger",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("action_request_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("action_type", sa.String(32), nullable=False),
        sa.Column("result_json", postgresql_jsonb(), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_action_ledger"),
        sa.ForeignKeyConstraint(
            ["action_request_id"],
            ["action_requests.id"],
            name="fk_action_ledger_action_request_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["tickets.id"], name="fk_action_ledger_ticket_id", ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "action_type IN ('CLOSE_TICKET', 'TRANSFER_TICKET')", name="ck_action_ledger_action_type"
        ),
        # 幂等边界：同一申请只能执行一次、同一幂等键只能落一次。
        sa.UniqueConstraint("action_request_id", name="uq_action_ledger_action_request_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_action_ledger_idempotency_key"),
    )
    op.create_index("ix_action_ledger_ticket_executed", "action_ledger", ["ticket_id", "executed_at"])


def downgrade() -> None:
    # 账本只追加且被 RESTRICT 约束保护：回滚会连同账本一起丢弃，因此明确记录这一点。
    op.drop_table("action_ledger")
    op.drop_table("action_requests")


def postgresql_jsonb() -> sa.types.TypeEngine[object]:
    """JSONB 在迁移里用方言类型表达，避免引入 ORM 模块。"""
    from sqlalchemy.dialects.postgresql import JSONB

    return JSONB()
