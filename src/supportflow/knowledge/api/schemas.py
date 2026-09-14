"""知识导入与检索接口契约。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from supportflow.knowledge.application.service import ImportResult
from supportflow.knowledge.domain.models import SearchResult


class ImportJobOut(BaseModel):
    id: str
    kind: str
    source_name: str
    status: str
    progress: int
    index_version: str
    duplicate: bool
    created_at: datetime

    @classmethod
    def of(cls, result: ImportResult) -> ImportJobOut:
        job, duplicate = result.job, result.duplicate
        return cls(
            id=str(job.id),
            kind=job.kind.value,
            source_name=job.source_name,
            status=job.status.value,
            progress=job.progress,
            index_version=job.index_version,
            duplicate=duplicate,
            created_at=job.created_at,
        )


class SearchOut(BaseModel):
    source_type: str
    source_id: str
    source_version: str
    chunk_id: str | None
    locator: str
    quote_text: str
    rank_no: int
    score: float
    full_text_rank: int | None
    vector_rank: int | None

    @classmethod
    def of(cls, result: SearchResult) -> SearchOut:
        citation = result.citation
        return cls(
            source_type=citation.source_type.value,
            source_id=str(citation.source_id),
            source_version=citation.source_version,
            chunk_id=str(citation.chunk_id) if citation.chunk_id else None,
            locator=citation.locator,
            quote_text=citation.quote_text,
            rank_no=citation.rank_no,
            score=citation.score,
            full_text_rank=result.full_text_rank,
            vector_rank=result.vector_rank,
        )


class SearchPageOut(BaseModel):
    query: str
    mode: str = "mock"
    items: list[SearchOut]
