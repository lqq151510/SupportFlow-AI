"""脱敏历史工单索引。

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-12
"""
# ruff: noqa: E501

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "history_tickets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_ref", sa.String(200), nullable=False),
        sa.Column("sanitized_question", sa.Text(), nullable=False),
        sa.Column("confirmed_resolution", sa.Text(), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("index_version", sa.String(64), nullable=False),
        sa.Column("tokenized_content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(64), nullable=False),
        sa.Column("tsv", postgresql.TSVECTOR(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_history_tickets"),
        sa.UniqueConstraint("source_hash", name="uq_history_tickets_source_hash"),
    )
    op.create_index("ix_history_tickets_tsv", "history_tickets", ["tsv"], postgresql_using="gin")
    op.execute("CREATE INDEX ix_history_tickets_embedding_hnsw ON history_tickets USING hnsw (embedding vector_cosine_ops)")


def downgrade() -> None:
    op.drop_table("history_tickets")
