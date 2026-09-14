"""知识库领域模型。领域层只表达来源、版本与检索结果，不依赖 ORM 或 Web 框架。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ImportKind(StrEnum):
    DOCUMENT = "DOCUMENT"
    HISTORY = "HISTORY"


class ImportStatus(StrEnum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SourceType(StrEnum):
    KNOWLEDGE = "KNOWLEDGE"
    HISTORY = "HISTORY"


@dataclass(frozen=True, slots=True)
class SourceCitation:
    source_type: SourceType
    source_id: UUID
    source_version: str
    chunk_id: UUID | None
    locator: str
    quote_text: str
    rank_no: int
    score: float


@dataclass(frozen=True, slots=True)
class SearchResult:
    citation: SourceCitation
    content: str
    full_text_rank: int | None
    vector_rank: int | None


@dataclass(frozen=True, slots=True)
class ImportJob:
    id: UUID
    kind: ImportKind
    source_name: str
    status: ImportStatus
    attempt: int
    progress: int
    error_code: str | None
    index_version: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class NewKnowledgeDocument:
    title: str
    mime_type: str
    object_key: str
    content_hash: str
    index_version: str
    embedding_model: str
    embedding_dim: int


@dataclass(frozen=True, slots=True)
class NewKnowledgeChunk:
    chunk_no: int
    content: str
    tokenized_content: str
    token_count: int
    locator: str
    index_version: str
    embedding: list[float]


@dataclass(frozen=True, slots=True)
class NewHistoryTicket:
    source_ref: str
    sanitized_question: str
    confirmed_resolution: str
    source_hash: str
    index_version: str
    tokenized_content: str
    embedding: list[float]
    resolved_at: datetime | None
