"""草稿版本表（PLAN §6 草稿审核 + 发布闭环）。

草稿是「agent 生成 → 人工审核 → 发布为正式回复」这一闭环的核心数据。每张工单维护一条
ACTIVE → PUBLISHED/ARCHIVED 的版本链；编辑派生新版本并归档旧版本，发布把 ACTIVE 置为
PUBLISHED（终态）。``citations`` 以 JSONB 快照本次检索的可溯源引用，前端不得伪造来源。

回滚：删除 ``drafts`` 表。草稿是业务派生数据，删除不损失工单主体事实；但与工单的
``ON DELETE CASCADE`` 由 FK 保证，单独 drop 表即可。

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-16
"""
# ruff: noqa: E501

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("author", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("editor_user_id", sa.Uuid(), nullable=True),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_drafts"),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["tickets.id"], name="fk_drafts_ticket_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["editor_user_id"], ["users.id"], name="fk_drafts_editor_user_id", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["published_by"], ["users.id"], name="fk_drafts_published_by", ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'PUBLISHED', 'ARCHIVED')", name="ck_drafts_status"
        ),
        sa.CheckConstraint("author IN ('agent', 'human')", name="ck_drafts_author"),
    )
    op.create_index("ix_drafts_ticket_version", "drafts", ["ticket_id", "version"])
    op.create_index("ix_drafts_ticket_status", "drafts", ["ticket_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_drafts_ticket_status", table_name="drafts")
    op.drop_index("ix_drafts_ticket_version", table_name="drafts")
    op.drop_table("drafts")
