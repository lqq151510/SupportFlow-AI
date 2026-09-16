"""知识模块端口。Agent 后续只能通过这些应用服务能力取得检索结果。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from supportflow.knowledge.domain.index_versions import IndexVersionSpec
from supportflow.knowledge.domain.models import (
    ImportJob,
    ImportKind,
    NewHistoryTicket,
    NewKnowledgeChunk,
    NewKnowledgeDocument,
    SearchResult,
)


class RetrievalPort(Protocol):
    def search(self, query: str, *, limit: int = 5) -> list[SearchResult]: ...


class KnowledgeRepositoryPort(Protocol):
    def document_exists(self, content_hash: str, index_version: str) -> bool: ...

    def create_job(
        self, *, kind: ImportKind, source_name: str, content_hash: str, index_version: str
    ) -> ImportJob: ...

    def finish_job(
        self, job_id: UUID, *, progress: int, error_code: str | None = None
    ) -> ImportJob: ...

    def add_document(self, document: NewKnowledgeDocument) -> UUID: ...

    def add_chunks(self, document_id: UUID, chunks: list[NewKnowledgeChunk]) -> list[UUID]: ...

    def add_chunk_vectors(
        self,
        chunk_ids: list[UUID],
        *,
        index_version: str,
        embedding_model: str,
        vectors: list[list[float]],
    ) -> None: ...

    def add_history_vector(
        self,
        ticket_id: UUID,
        *,
        index_version: str,
        embedding_model: str,
        vector: list[float],
    ) -> None: ...

    def search_versioned(
        self,
        *,
        query_tokens: str,
        embedding: list[float],
        index_version: str,
        limit: int,
    ) -> list[SearchResult]: ...

    def mark_document_indexed(self, document_id: UUID) -> None: ...

    def history_exists(self, source_hash: str) -> bool: ...

    def add_history(self, ticket: NewHistoryTicket) -> UUID: ...

    def search(
        self, *, query_tokens: str, embedding: list[float], limit: int
    ) -> list[SearchResult]: ...

class EmbeddingProviderPort(Protocol):
    """知识模块对「嵌入能力 + 当前索引版本」的唯一依赖。

    刻意把两者放在同一个端口上：索引版本决定了向量该写进哪个存储、多少维，
    而向量又只能来自与该版本匹配的模型。分开注入迟早会出现「版本说 1024、
    向量却是 64 维」这种自相矛盾的组合。
    """

    def active_index_version(self) -> IndexVersionSpec:
        """当前启用的索引版本。没有配置 Embedding 时返回旧版（Mock）规格。"""
        ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """把文本批量向量化。

        实现必须保证返回向量的维度等于 :meth:`active_index_version` 的 ``dimension`` ——
        维度不符属于配置错误，应在连接测试阶段就被拦下。
        """
        ...
