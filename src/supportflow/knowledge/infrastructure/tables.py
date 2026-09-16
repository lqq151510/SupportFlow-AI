"""knowledge 模块 ORM 表。向量维度属于索引版本契约，S3 更换模型时必须新建版本。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from supportflow.knowledge.application.tokenization import EMBEDDING_DIMENSION
from supportflow.knowledge.domain.index_versions import VERSIONED_EMBEDDING_DIMENSION
from supportflow.shared.clock import utcnow
from supportflow.shared.db import Base


class ImportJobRow(Base):
    __tablename__ = "import_jobs"
    __table_args__ = (
        CheckConstraint("kind IN ('DOCUMENT', 'HISTORY')", name="ck_import_jobs_kind"),
        CheckConstraint(
            "status IN ('PROCESSING', 'COMPLETED', 'FAILED')",
            name="ck_import_jobs_status",
        ),
        CheckConstraint("progress BETWEEN 0 AND 100", name="ck_import_jobs_progress"),
        Index("ix_import_jobs_kind_status_created", "kind", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(16))
    source_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16))
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    index_version: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class KnowledgeDocumentRow(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('INDEXING', 'INDEXED', 'FAILED')",
            name="ck_knowledge_documents_status",
        ),
        UniqueConstraint(
            "content_hash",
            "index_version",
            name="uq_knowledge_documents_hash_version",
        ),
        Index("ix_knowledge_documents_status_created", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(120))
    object_key: Mapped[str] = mapped_column(String(512))
    content_hash: Mapped[str] = mapped_column(String(64))
    index_version: Mapped[str] = mapped_column(String(64))
    embedding_model: Mapped[str] = mapped_column(String(120))
    embedding_dim: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class KnowledgeChunkRow(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "chunk_no",
            name="uq_knowledge_chunks_document_chunk",
        ),
        Index("ix_knowledge_chunks_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_knowledge_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE")
    )
    chunk_no: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    tokenized_content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer)
    locator: Mapped[str] = mapped_column(String(128))
    index_version: Mapped[str] = mapped_column(String(64))
    # 旧版（Mock）向量。新版索引版本的文档**不写这一列**（留 NULL），
    # 它们的向量在 knowledge_chunk_vectors 里，两者互不读取。
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIMENSION), nullable=True
    )
    tsv: Mapped[object] = mapped_column(TSVECTOR)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class KnowledgeChunkVectorRow(Base):
    """新版索引版本的切片向量存储。

    为什么单独一张表而不是给 ``knowledge_chunks`` 加一列：

    - ``vector`` 列的维度是**物理契约**，无法在一列里同时容纳 64 维与 1024 维；
    - 主键 ``(chunk_id, index_version)`` 让同一切片可以同时拥有多个版本的向量，
      重新索引不会破坏旧版本的数据（expand-contract）；
    - 检索**必须**带上 ``index_version`` 过滤，因此跨模型比较向量在结构上不可能发生
      （AGENTS.md §7）。

    该表列维度固定为 :data:`VERSIONED_EMBEDDING_DIMENSION`；换维度需要新迁移。
    """

    __tablename__ = "knowledge_chunk_vectors"
    __table_args__ = (
        Index(
            "ix_knowledge_chunk_vectors_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_knowledge_chunk_vectors_version", "index_version"),
    )

    chunk_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_chunks.id", ondelete="CASCADE"), primary_key=True
    )
    index_version: Mapped[str] = mapped_column(String(64), primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(VERSIONED_EMBEDDING_DIMENSION))
    embedding_model: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class HistoryTicketVectorRow(Base):
    """新版索引版本的历史工单向量存储。理由同 ``KnowledgeChunkVectorRow``。"""

    __tablename__ = "history_ticket_vectors"
    __table_args__ = (
        Index(
            "ix_history_ticket_vectors_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_history_ticket_vectors_version", "index_version"),
    )

    ticket_id: Mapped[UUID] = mapped_column(
        ForeignKey("history_tickets.id", ondelete="CASCADE"), primary_key=True
    )
    index_version: Mapped[str] = mapped_column(String(64), primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(VERSIONED_EMBEDDING_DIMENSION))
    embedding_model: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class HistoryTicketRow(Base):
    __tablename__ = "history_tickets"
    __table_args__ = (
        Index("ix_history_tickets_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_history_tickets_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_ref: Mapped[str] = mapped_column(String(200))
    sanitized_question: Mapped[str] = mapped_column(Text)
    confirmed_resolution: Mapped[str] = mapped_column(Text)
    source_hash: Mapped[str] = mapped_column(String(64), unique=True)
    index_version: Mapped[str] = mapped_column(String(64))
    tokenized_content: Mapped[str] = mapped_column(Text)
    # 旧版（Mock）向量。新版索引版本的文档**不写这一列**（留 NULL），
    # 它们的向量在 knowledge_chunk_vectors 里，两者互不读取。
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIMENSION), nullable=True
    )
    tsv: Mapped[object] = mapped_column(TSVECTOR)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
