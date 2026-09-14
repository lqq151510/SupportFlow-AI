"""知识导入、检索及来源溯源应用服务。"""

from __future__ import annotations

import csv
import hashlib
import io
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

from docx import Document
from pypdf import PdfReader

from supportflow.identity.domain.models import Principal
from supportflow.knowledge.application.tokenization import (
    EMBEDDING_DIMENSION,
    mock_embedding,
    tokenize,
)
from supportflow.knowledge.domain.models import (
    ImportJob,
    ImportKind,
    ImportStatus,
    NewHistoryTicket,
    NewKnowledgeChunk,
    NewKnowledgeDocument,
    SearchResult,
)
from supportflow.knowledge.domain.ports import KnowledgeRepositoryPort
from supportflow.shared.errors import Forbidden, InvalidRequest
from supportflow.shared.idempotency import IdempotencyPort, ReplayedResponse, fingerprint

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
DEFAULT_INDEX_VERSION = "mock-v1"
MOCK_EMBEDDING_MODEL = "mock-hash-64"
CHUNK_SIZE = 600
CHUNK_OVERLAP = 100
DOCUMENT_IMPORT_SCOPE = "POST /api/v1/knowledge/imports"
HISTORY_IMPORT_SCOPE = "POST /api/v1/knowledge/history/imports"
_DOCUMENT_MIME_TYPES = {
    ".txt": {"text/plain"},
    ".md": {"text/markdown", "text/plain"},
    ".csv": {"text/csv", "application/csv"},
    ".pdf": {"application/pdf"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
}


@dataclass(frozen=True, slots=True)
class ImportResult:
    job: ImportJob
    duplicate: bool


class KnowledgeService:
    def __init__(
        self,
        repository: KnowledgeRepositoryPort,
        idempotency: IdempotencyPort,
        *,
        upload_dir: Path,
    ) -> None:
        self._repository = repository
        self._idempotency = idempotency
        self._upload_dir = upload_dir

    def import_document(
        self,
        principal: Principal,
        *,
        filename: str,
        content_type: str | None,
        raw: bytes,
        idempotency_key: str,
    ) -> ImportResult:
        self._require_admin(principal)
        self._validate_upload(filename, raw)
        content_hash = hashlib.sha256(raw).hexdigest()
        replayed = self._idempotency.reserve(
            DOCUMENT_IMPORT_SCOPE,
            idempotency_key,
            fingerprint({"filename": filename, "content_hash": content_hash}),
        )
        if replayed is not None:
            return self._as_replay(replayed)
        # 端口契约返回 bool：此处必须按真值判断。曾用 ``is not None`` 判断，
        # 因 bool 永远不是 None，导致每次导入都被误判为重复文档而跳过入库。
        duplicated = self._repository.document_exists(content_hash, DEFAULT_INDEX_VERSION)
        job = self._repository.create_job(
            kind=ImportKind.DOCUMENT,
            source_name=filename,
            content_hash=content_hash,
            index_version=DEFAULT_INDEX_VERSION,
        )
        if duplicated:
            finished = self._repository.finish_job(job.id, progress=100)
            result = ImportResult(finished, duplicate=True)
            self._complete_idempotency(DOCUMENT_IMPORT_SCOPE, idempotency_key, result)
            return result
        try:
            extracted, mime_type = self._extract(filename, content_type, raw)
            if not extracted.strip():
                raise InvalidRequest("文件未提取到可索引文本")
            object_key = self._store_raw(content_hash, filename, raw)
            document_id = self._repository.add_document(
                NewKnowledgeDocument(
                    title=Path(filename).stem[:255],
                    mime_type=mime_type,
                    object_key=object_key,
                    content_hash=content_hash,
                    index_version=DEFAULT_INDEX_VERSION,
                    embedding_model=MOCK_EMBEDDING_MODEL,
                    embedding_dim=EMBEDDING_DIMENSION,
                )
            )
            chunks = _chunk_text(extracted)
            self._repository.add_chunks(
                document_id,
                [
                    NewKnowledgeChunk(
                        chunk_no=number,
                        content=chunk,
                        tokenized_content=tokenize(chunk),
                        token_count=len(tokenize(chunk).split()),
                        locator=f"chunk:{number}",
                        index_version=DEFAULT_INDEX_VERSION,
                        embedding=mock_embedding(chunk),
                    )
                    for number, chunk in enumerate(chunks, start=1)
                ],
            )
            self._repository.mark_document_indexed(document_id)
            finished = self._repository.finish_job(job.id, progress=100)
            result = ImportResult(finished, duplicate=False)
            self._complete_idempotency(DOCUMENT_IMPORT_SCOPE, idempotency_key, result)
            return result
        except InvalidRequest:
            self._repository.finish_job(job.id, progress=0, error_code="import_invalid")
            raise

    def import_history(
        self,
        principal: Principal,
        *,
        filename: str,
        raw: bytes,
        idempotency_key: str,
    ) -> ImportResult:
        self._require_admin(principal)
        if not filename.lower().endswith((".csv", ".jsonl")):
            raise InvalidRequest("历史工单只支持 CSV 或 JSONL")
        self._validate_upload(filename, raw)
        content_hash = hashlib.sha256(raw).hexdigest()
        replayed = self._idempotency.reserve(
            HISTORY_IMPORT_SCOPE,
            idempotency_key,
            fingerprint({"filename": filename, "content_hash": content_hash}),
        )
        if replayed is not None:
            return self._as_replay(replayed)
        job = self._repository.create_job(
            kind=ImportKind.HISTORY,
            source_name=filename,
            content_hash=content_hash,
            index_version=DEFAULT_INDEX_VERSION,
        )
        inserted = 0
        try:
            for entry in _parse_history(filename, raw):
                question = str(entry.get("question", "")).strip()
                resolution = str(entry.get("resolution", "")).strip()
                source_ref = str(entry.get("source_ref", "")).strip()
                if not (question and resolution and source_ref):
                    raise InvalidRequest("每条历史工单都必须包含 source_ref、question、resolution")
                row_hash = hashlib.sha256(
                    f"{source_ref}\n{question}\n{resolution}".encode()
                ).hexdigest()
                if self._repository.history_exists(row_hash):
                    continue
                content = f"问题：{question}\n处理结果：{resolution}"
                self._repository.add_history(
                    NewHistoryTicket(
                        source_ref=source_ref,
                        sanitized_question=question,
                        confirmed_resolution=resolution,
                        source_hash=row_hash,
                        index_version=DEFAULT_INDEX_VERSION,
                        tokenized_content=tokenize(content),
                        embedding=mock_embedding(content),
                        resolved_at=_parse_time(entry.get("resolved_at")),
                    )
                )
                inserted += 1
            finished = self._repository.finish_job(job.id, progress=100)
            result = ImportResult(finished, duplicate=inserted == 0)
            self._complete_idempotency(HISTORY_IMPORT_SCOPE, idempotency_key, result)
            return result
        except InvalidRequest:
            self._repository.finish_job(job.id, progress=0, error_code="history_row_invalid")
            raise

    def search(self, principal: Principal, query: str, *, limit: int = 5) -> list[SearchResult]:
        if not principal.is_staff:
            raise Forbidden("仅坐席与管理员可以检索内部知识")
        return self.retrieve_for_run(query, limit=limit)

    def retrieve_for_run(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        """**运行内部**检索入口：供 Agent Worker 在执行运行图时调用。

        Agent 运行没有 HTTP 调用者身份，而检索结果只在服务端使用（不会直接下发给客户），
        因此这里不做角色判定；HTTP 侧一律走 ``search``，权限判定仍然只在那一条路径上。

        与 ``search`` 的另一处差异：查询无法分词时返回空列表而不是 400 —— 运行内部
        把「检索不到证据」当作一种正常结果，由状态图判定转人工。
        """
        normalized = tokenize(query)
        if not normalized:
            return []
        return self._repository.search(
            query_tokens=normalized,
            embedding=mock_embedding(query),
            limit=limit,
        )

    def _store_raw(self, content_hash: str, filename: str, raw: bytes) -> str:
        suffix = Path(filename).suffix.lower()
        safe_name = f"{content_hash}{suffix}"
        self._upload_dir.mkdir(parents=True, exist_ok=True)
        target = self._upload_dir / safe_name
        if not target.exists():
            target.write_bytes(raw)
        return safe_name

    @staticmethod
    def _require_admin(principal: Principal) -> None:
        if not principal.is_admin:
            raise Forbidden("仅管理员可以导入知识与历史工单")

    @staticmethod
    def _validate_upload(filename: str, raw: bytes) -> None:
        if not filename or Path(filename).name != filename:
            raise InvalidRequest("文件名不合法")
        if not raw:
            raise InvalidRequest("上传文件不能为空")
        if len(raw) > MAX_UPLOAD_BYTES:
            raise InvalidRequest("单文件不得超过 20MB")

    @staticmethod
    def _extract(filename: str, content_type: str | None, raw: bytes) -> tuple[str, str]:
        suffix = Path(filename).suffix.lower()
        accepted_mime_types = _DOCUMENT_MIME_TYPES.get(suffix)
        if accepted_mime_types is None:
            raise InvalidRequest("仅支持 TXT、Markdown、CSV、PDF 和 DOCX")
        if content_type and content_type not in {
            "application/octet-stream",
            *accepted_mime_types,
        }:
            raise InvalidRequest("文件 MIME 类型与扩展名不匹配")
        if suffix in {".txt", ".md"}:
            return raw.decode("utf-8"), "text/markdown" if suffix == ".md" else "text/plain"
        if suffix == ".csv":
            return _faq_as_text(raw), "text/csv"
        if suffix == ".pdf":
            if not raw.startswith(b"%PDF-"):
                raise InvalidRequest("PDF 文件签名不正确")
            reader = PdfReader(io.BytesIO(raw))
            return (
                "\n\n".join(page.extract_text() or "" for page in reader.pages),
                "application/pdf",
            )
        if suffix == ".docx":
            if not raw.startswith(b"PK"):
                raise InvalidRequest("DOCX 文件签名不正确")
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    if "word/document.xml" not in archive.namelist():
                        raise InvalidRequest("DOCX 文件结构不正确")
                document = Document(io.BytesIO(raw))
            except zipfile.BadZipFile as exc:
                raise InvalidRequest("DOCX 文件结构不正确") from exc
            return "\n".join(paragraph.text for paragraph in document.paragraphs), (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        raise AssertionError("已校验的扩展名必须可提取")

    def _complete_idempotency(self, scope: str, idempotency_key: str, result: ImportResult) -> None:
        job = result.job
        self._idempotency.complete(
            scope,
            idempotency_key,
            status_code=202,
            body={
                "id": str(job.id),
                "kind": job.kind.value,
                "source_name": job.source_name,
                "status": job.status.value,
                "progress": job.progress,
                "index_version": job.index_version,
                "duplicate": result.duplicate,
                "created_at": job.created_at.isoformat(),
            },
        )

    @staticmethod
    def _as_replay(replayed: ReplayedResponse) -> ImportResult:
        body = replayed.body
        return ImportResult(
            ImportJob(
                id=UUID(str(body["id"])),
                kind=ImportKind(str(body["kind"])),
                source_name=str(body["source_name"]),
                status=ImportStatus(str(body["status"])),
                attempt=1,
                progress=int(body["progress"]),
                error_code=None,
                index_version=str(body["index_version"]),
                created_at=datetime.fromisoformat(str(body["created_at"])),
            ),
            duplicate=bool(body["duplicate"]),
        )


def _chunk_text(content: str) -> list[str]:
    sentences = [
        piece for part in re.split(r"(?<=[。！？.!?])|\n+", content) if (piece := part.strip())
    ]
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    sentence_parts = [piece for original in sentences for piece in _split_long_sentence(original)]
    for sentence in sentence_parts:
        sentence_tokens = len(tokenize(sentence).split())
        if current and current_tokens + sentence_tokens > CHUNK_SIZE:
            chunks.append("\n".join(current))
            overlap = _overlap_sentences(current, max_tokens=CHUNK_SIZE - sentence_tokens)
            current = [*overlap, sentence]
            current_tokens = sum(len(tokenize(item).split()) for item in current)
        else:
            current.append(sentence)
            current_tokens += sentence_tokens
    if current:
        chunks.append("\n".join(current))
    return chunks


def _overlap_sentences(sentences: list[str], *, max_tokens: int) -> list[str]:
    overlap: list[str] = []
    token_count = 0
    for sentence in reversed(sentences):
        count = len(tokenize(sentence).split())
        if token_count + count > CHUNK_OVERLAP or token_count + count > max_tokens:
            break
        overlap.append(sentence)
        token_count += count
    return list(reversed(overlap))


def _split_long_sentence(sentence: str) -> list[str]:
    """连续中文长句没有天然分隔符时，按最多约 600 个 jieba token 兜底切分。"""
    tokens = tokenize(sentence).split()
    if len(tokens) <= CHUNK_SIZE:
        return [sentence]
    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        chunks.append(" ".join(tokens[start : start + CHUNK_SIZE]))
        if start + CHUNK_SIZE >= len(tokens):
            break
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def _faq_as_text(raw: bytes) -> str:
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    if not rows or not {"question", "answer"}.issubset(rows[0]):
        raise InvalidRequest("FAQ CSV 必须包含 question 和 answer 列")
    return "\n\n".join(f"问题：{row['question']}\n答案：{row['answer']}" for row in rows)


def _parse_history(filename: str, raw: bytes) -> list[dict[str, object]]:
    if filename.lower().endswith(".csv"):
        return [dict(row) for row in csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))]
    import json

    try:
        return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    except json.JSONDecodeError as exc:
        raise InvalidRequest("历史 JSONL 格式不正确") from exc


def _parse_time(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidRequest("resolved_at 必须是 ISO 8601 时间") from exc
