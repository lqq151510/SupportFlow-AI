"""知识导入和混合检索的 PostgreSQL 实现。"""
# ruff: noqa: E501

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from supportflow.knowledge.domain.models import (
    ImportJob,
    ImportKind,
    ImportStatus,
    NewHistoryTicket,
    NewKnowledgeChunk,
    NewKnowledgeDocument,
    SearchResult,
    SourceCitation,
    SourceType,
)
from supportflow.knowledge.infrastructure.tables import (
    HistoryTicketRow,
    ImportJobRow,
    KnowledgeChunkRow,
    KnowledgeDocumentRow,
)

Candidate = dict[str, Any]
_ROUTES = ("full_text", "vector")


def _to_job(row: ImportJobRow) -> ImportJob:
    return ImportJob(
        id=row.id,
        kind=ImportKind(row.kind),
        source_name=row.source_name,
        status=ImportStatus(row.status),
        attempt=row.attempt,
        progress=row.progress,
        error_code=row.error_code,
        index_version=row.index_version,
        created_at=row.created_at,
    )


class SqlAlchemyKnowledgeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def document_exists(self, content_hash: str, index_version: str) -> bool:
        return (
            self._session.query(KnowledgeDocumentRow)
            .filter_by(content_hash=content_hash, index_version=index_version)
            .first()
            is not None
        )

    def create_job(
        self, *, kind: ImportKind, source_name: str, content_hash: str, index_version: str
    ) -> ImportJob:
        row = ImportJobRow(
            kind=kind.value,
            source_name=source_name,
            status=ImportStatus.PROCESSING.value,
            content_hash=content_hash,
            index_version=index_version,
        )
        self._session.add(row)
        self._session.flush()
        return _to_job(row)

    def finish_job(
        self, job_id: UUID, *, progress: int, error_code: str | None = None
    ) -> ImportJob:
        row = self._session.get(ImportJobRow, job_id)
        if row is None:  # pragma: no cover - 同一事务刚创建的任务不可能丢失
            raise RuntimeError(f"导入任务不存在: {job_id}")
        row.progress = progress
        row.error_code = error_code
        row.status = (
            ImportStatus.COMPLETED.value if error_code is None else ImportStatus.FAILED.value
        )
        self._session.flush()
        return _to_job(row)

    def add_document(self, document: NewKnowledgeDocument) -> UUID:
        row = KnowledgeDocumentRow(
            title=document.title,
            mime_type=document.mime_type,
            object_key=document.object_key,
            content_hash=document.content_hash,
            index_version=document.index_version,
            embedding_model=document.embedding_model,
            embedding_dim=document.embedding_dim,
            status="INDEXING",
        )
        self._session.add(row)
        self._session.flush()
        return row.id

    def add_chunks(self, document_id: UUID, chunks: list[NewKnowledgeChunk]) -> None:
        self._session.add_all(
            [
                KnowledgeChunkRow(
                    document_id=document_id,
                    chunk_no=chunk.chunk_no,
                    content=chunk.content,
                    tokenized_content=chunk.tokenized_content,
                    token_count=chunk.token_count,
                    locator=chunk.locator,
                    index_version=chunk.index_version,
                    embedding=chunk.embedding,
                    tsv=text("to_tsvector('simple', :tokens)").bindparams(
                        tokens=chunk.tokenized_content
                    ),
                )
                for chunk in chunks
            ]
        )

    def mark_document_indexed(self, document_id: UUID) -> None:
        row = self._session.get(KnowledgeDocumentRow, document_id)
        if row is None:  # pragma: no cover - 调用方刚插入了文档
            raise RuntimeError(f"知识文档不存在: {document_id}")
        row.status = "INDEXED"

    def history_exists(self, source_hash: str) -> bool:
        stmt = self._session.query(HistoryTicketRow.id).filter_by(source_hash=source_hash)
        return stmt.first() is not None

    def add_history(self, ticket: NewHistoryTicket) -> None:
        row = HistoryTicketRow(
            source_ref=ticket.source_ref,
            sanitized_question=ticket.sanitized_question,
            confirmed_resolution=ticket.confirmed_resolution,
            source_hash=ticket.source_hash,
            index_version=ticket.index_version,
            tokenized_content=ticket.tokenized_content,
            embedding=ticket.embedding,
            tsv=text("to_tsvector('simple', :tokens)").bindparams(tokens=ticket.tokenized_content),
            resolved_at=ticket.resolved_at,
        )
        self._session.add(row)

    def search(
        self, *, query_tokens: str, embedding: list[float], limit: int
    ) -> list[SearchResult]:
        """全文与向量各取 20，应用层 RRF 合并，排序规则可以由单测直接固定。"""
        params = {"query": query_tokens, "embedding": str(embedding), "candidate_limit": 20}
        full_text = self._query_candidates(_FULL_TEXT, params)
        vector = self._query_candidates(_VECTOR, params)
        return _rrf(full_text, vector, limit)

    def _query_candidates(self, statement: str, params: dict[str, object]) -> list[Candidate]:
        rows = self._session.execute(text(statement), params).mappings().all()
        return [dict(row) for row in rows]


_FULL_TEXT = """
WITH candidates AS (
SELECT 'KNOWLEDGE' AS source_type, kc.id AS chunk_id, kd.id AS source_id,
       kd.index_version, kc.locator, kc.content,
       ts_rank_cd(kc.tsv, plainto_tsquery('simple', :query)) AS score
FROM knowledge_chunks kc JOIN knowledge_documents kd ON kd.id = kc.document_id
WHERE kd.status = 'INDEXED' AND kc.tsv @@ plainto_tsquery('simple', :query)
UNION ALL
SELECT 'HISTORY' AS source_type, NULL AS chunk_id, ht.id AS source_id,
       ht.index_version, ht.source_ref AS locator,
       concat('问题：', ht.sanitized_question, E'\\n处理结果：', ht.confirmed_resolution) AS content,
       ts_rank_cd(ht.tsv, plainto_tsquery('simple', :query)) AS score
FROM history_tickets ht
WHERE ht.tsv @@ plainto_tsquery('simple', :query)
)
SELECT * FROM candidates
ORDER BY score DESC, source_id
LIMIT :candidate_limit
"""
_VECTOR = """
WITH candidates AS (
SELECT 'KNOWLEDGE' AS source_type, kc.id AS chunk_id, kd.id AS source_id,
       kd.index_version, kc.locator, kc.content,
       1 - (kc.embedding <=> CAST(:embedding AS vector)) AS score
FROM knowledge_chunks kc JOIN knowledge_documents kd ON kd.id = kc.document_id
WHERE kd.status = 'INDEXED'
UNION ALL
SELECT 'HISTORY' AS source_type, NULL AS chunk_id, ht.id AS source_id,
       ht.index_version, ht.source_ref AS locator,
       concat('问题：', ht.sanitized_question, E'\\n处理结果：', ht.confirmed_resolution) AS content,
       1 - (ht.embedding <=> CAST(:embedding AS vector)) AS score
FROM history_tickets ht
)
SELECT * FROM candidates
ORDER BY score DESC, source_id
LIMIT :candidate_limit
"""


def _rrf(full_text: list[Candidate], vector: list[Candidate], limit: int) -> list[SearchResult]:
    entries: dict[tuple[str, str], Candidate] = {}
    for route, rows in (("full_text", full_text), ("vector", vector)):
        for rank, row in enumerate(rows, start=1):
            key = (str(row["source_type"]), str(row["chunk_id"] or row["source_id"]))
            entry = entries.setdefault(key, {**row, "full_text": None, "vector": None})
            entry[route] = rank
    ranked = sorted(entries.values(), key=_rrf_score, reverse=True)
    return [_to_result(item, rank) for rank, item in enumerate(ranked[:limit], start=1)]


def _rrf_score(item: Candidate) -> float:
    return sum(1 / (60 + int(item[route])) for route in _ROUTES if item[route] is not None)


def _to_result(item: Candidate, rank: int) -> SearchResult:
    chunk_id = UUID(str(item["chunk_id"])) if item["chunk_id"] else None
    citation = SourceCitation(
        source_type=SourceType(str(item["source_type"])),
        source_id=UUID(str(item["source_id"])),
        source_version=str(item["index_version"]),
        chunk_id=chunk_id,
        locator=str(item["locator"]),
        quote_text=str(item["content"])[:400],
        rank_no=rank,
        score=_rrf_score(item),
    )
    return SearchResult(
        citation=citation,
        content=str(item["content"]),
        full_text_rank=item["full_text"],
        vector_rank=item["vector"],
    )
