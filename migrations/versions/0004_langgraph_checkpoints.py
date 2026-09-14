"""LangGraph PostgreSQL 检查点。

这些表结构与 ``langgraph-checkpoint-postgres==3.1.2`` 的同步 saver 契约保持一致。
由 Alembic 创建，禁止在 Worker 启动时调用 ``PostgresSaver.setup()`` 执行运行时 DDL。

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("checkpoint_migrations", sa.Column("v", sa.Integer(), primary_key=True))
    op.create_table(
        "checkpoints",
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("checkpoint_ns", sa.Text(), nullable=False, server_default=""),
        sa.Column("checkpoint_id", sa.Text(), nullable=False),
        sa.Column("parent_checkpoint_id", sa.Text()),
        sa.Column("type", sa.Text()),
        sa.Column("checkpoint", postgresql.JSONB(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.PrimaryKeyConstraint("thread_id", "checkpoint_ns", "checkpoint_id"),
    )
    op.create_table(
        "checkpoint_blobs",
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("checkpoint_ns", sa.Text(), nullable=False, server_default=""),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("blob", sa.LargeBinary()),
        sa.PrimaryKeyConstraint("thread_id", "checkpoint_ns", "channel", "version"),
    )
    op.create_table(
        "checkpoint_writes",
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("checkpoint_ns", sa.Text(), nullable=False, server_default=""),
        sa.Column("checkpoint_id", sa.Text(), nullable=False),
        sa.Column("task_id", sa.Text(), nullable=False),
        sa.Column("idx", sa.Integer(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("type", sa.Text()),
        sa.Column("blob", sa.LargeBinary(), nullable=False),
        sa.Column("task_path", sa.Text(), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("thread_id", "checkpoint_ns", "checkpoint_id", "task_id", "idx"),
    )
    op.bulk_insert(sa.table("checkpoint_migrations", sa.column("v", sa.Integer())), [{"v": value} for value in range(10)])
    with op.get_context().autocommit_block():
        op.execute("CREATE INDEX CONCURRENTLY checkpoints_thread_id_idx ON checkpoints(thread_id)")
        op.execute("CREATE INDEX CONCURRENTLY checkpoint_blobs_thread_id_idx ON checkpoint_blobs(thread_id)")
        op.execute("CREATE INDEX CONCURRENTLY checkpoint_writes_thread_id_idx ON checkpoint_writes(thread_id)")


def downgrade() -> None:
    op.drop_table("checkpoint_writes")
    op.drop_table("checkpoint_blobs")
    op.drop_table("checkpoints")
    op.drop_table("checkpoint_migrations")
