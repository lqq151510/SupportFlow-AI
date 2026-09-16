"""新版索引版本的向量存储（1024 维，按索引版本隔离）。

**为什么是新表而不是给旧表加列**：PostgreSQL 的 ``vector`` 列维度固定，一列无法同时
容纳 64 维（旧版 Mock）与 1024 维（``BAAI/bge-m3``）。而 `AGENTS.md` §7 要求
「不得在同一向量列混用不同模型的向量」，因此新版单独建表，列维度只服务这一个索引版本。

设计要点：

- 主键 ``(chunk_id, index_version)``：同一切片可并存多个版本的向量，重新索引不破坏
  旧版本数据，符合 expand-contract；
- 检索**必须**带 ``index_version`` 过滤 → 跨模型比较向量在结构上不可能发生；
- 每表一个 HNSW 索引（余弦距离），外加 ``index_version`` 上的普通索引支撑过滤。

访问路径：

- 向量检索：``JOIN ... WHERE index_version = :v ORDER BY embedding <=> :q LIMIT n``
  → HNSW 索引 + 版本过滤；
- 重索引/回填：按 ``index_version`` 扫描或删除。

回滚：``downgrade`` 直接删两张表。旧版 64 维列与既有数据**不受影响**，
因此本迁移回滚不丢任何既有检索能力。

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-16
"""
# ruff: noqa: E501

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: 与 ``knowledge.domain.index_versions`` 的两个常量保持一致。
#: 迁移中刻意写死数值：迁移是历史快照，不应随业务常量变动而改变语义。
VERSIONED_DIMENSION = 1024
LEGACY_DIMENSION = 64


def upgrade() -> None:
    op.create_table(
        "knowledge_chunk_vectors",
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("index_version", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(VERSIONED_DIMENSION), nullable=False),
        sa.Column("embedding_model", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("chunk_id", "index_version", name="pk_knowledge_chunk_vectors"),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["knowledge_chunks.id"],
            name="fk_knowledge_chunk_vectors_chunk_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_knowledge_chunk_vectors_version", "knowledge_chunk_vectors", ["index_version"]
    )
    op.execute(
        "CREATE INDEX ix_knowledge_chunk_vectors_embedding_hnsw "
        "ON knowledge_chunk_vectors USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "history_ticket_vectors",
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("index_version", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(VERSIONED_DIMENSION), nullable=False),
        sa.Column("embedding_model", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("ticket_id", "index_version", name="pk_history_ticket_vectors"),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["history_tickets.id"],
            name="fk_history_ticket_vectors_ticket_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_history_ticket_vectors_version", "history_ticket_vectors", ["index_version"])
    op.execute(
        "CREATE INDEX ix_history_ticket_vectors_embedding_hnsw "
        "ON history_ticket_vectors USING hnsw (embedding vector_cosine_ops)"
    )

    # 旧版向量列改为可空：新版索引版本的文档**不写**这一列（留 NULL），它们的向量在新表里。
    # 旧版文档照常写入，因此这是 expand 而不是破坏；旧列与新列互不读取。
    op.alter_column("knowledge_chunks", "embedding", existing_type=Vector(LEGACY_DIMENSION), nullable=True)
    op.alter_column("history_tickets", "embedding", existing_type=Vector(LEGACY_DIMENSION), nullable=True)


def downgrade() -> None:
    # 回滚前需先清掉 NULL 值（新版文档在旧列上就是 NULL），否则恢复 NOT NULL 会失败。
    op.execute("DELETE FROM knowledge_chunk_vectors")
    op.execute("DELETE FROM history_ticket_vectors")
    op.alter_column(
        "history_tickets", "embedding", existing_type=Vector(LEGACY_DIMENSION), nullable=False
    )
    op.alter_column(
        "knowledge_chunks", "embedding", existing_type=Vector(LEGACY_DIMENSION), nullable=False
    )
    op.drop_table("history_ticket_vectors")
    op.drop_table("knowledge_chunk_vectors")
