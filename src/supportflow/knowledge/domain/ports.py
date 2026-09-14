"""知识模块端口。Agent 后续只能通过这些应用服务能力取得检索结果。"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

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

    def add_chunks(self, document_id: UUID, chunks: list[NewKnowledgeChunk]) -> None: ...

    def mark_document_indexed(self, document_id: UUID) -> None: ...

    def history_exists(self, source_hash: str) -> bool: ...

    def add_history(self, ticket: NewHistoryTicket) -> None: ...

    def search(
        self, *, query_tokens: str, embedding: list[float], limit: int
    ) -> list[SearchResult]: ...
