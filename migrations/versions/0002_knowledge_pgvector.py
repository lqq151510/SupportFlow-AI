"""知识文档、切片、导入任务与 pgvector 双索引。

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-12

全文列存入应用层 jieba 分词后的空格 token，数据库使用 ``simple`` 配置生成 tsvector。
这样 GIN 负责词级中文召回；向量列使用固定 64 维 Mock 索引版本。S3 改真实
Embedding 时必须新建 index_version，不得向该列混写不同维度或模型的向量。
"""
# ruff: noqa: E501

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("index_version", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('DOCUMENT', 'HISTORY')", name="ck_import_jobs_kind"),
        sa.CheckConstraint("status IN ('PROCESSING', 'COMPLETED', 'FAILED')", name="ck_import_jobs_status"),
        sa.CheckConstraint("progress BETWEEN 0 AND 100", name="ck_import_jobs_progress"),
        sa.PrimaryKeyConstraint("id", name="pk_import_jobs"),
    )
    op.create_index("ix_import_jobs_kind_status_created", "import_jobs", ["kind", "status", "created_at"])

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(120), nullable=False),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("index_version", sa.String(64), nullable=False),
        sa.Column("embedding_model", sa.String(120), nullable=False),
        sa.Column("embedding_dim", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('INDEXING', 'INDEXED', 'FAILED')", name="ck_knowledge_documents_status"),
        sa.PrimaryKeyConstraint("id", name="pk_knowledge_documents"),
        sa.UniqueConstraint("content_hash", "index_version", name="uq_knowledge_documents_hash_version"),
    )
    op.create_index("ix_knowledge_documents_status_created", "knowledge_documents", ["status", "created_at"])

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_no", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tokenized_content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("locator", sa.String(128), nullable=False),
        sa.Column("index_version", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(64), nullable=False),
        sa.Column("tsv", postgresql.TSVECTOR(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"], ondelete="CASCADE", name="fk_knowledge_chunks_document"),
        sa.PrimaryKeyConstraint("id", name="pk_knowledge_chunks"),
        sa.UniqueConstraint("document_id", "chunk_no", name="uq_knowledge_chunks_document_chunk"),
    )
    op.create_index("ix_knowledge_chunks_tsv", "knowledge_chunks", ["tsv"], postgresql_using="gin")
    op.execute("CREATE INDEX ix_knowledge_chunks_embedding_hnsw ON knowledge_chunks USING hnsw (embedding vector_cosine_ops)")


def downgrade() -> None:
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
    op.drop_table("import_jobs")
    # vector 扩展可能由其他迁移使用，降级时不删除。
