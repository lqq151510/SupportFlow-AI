"""幂等键存储。

这是**跨模块关注点**，因此刻意放在 ``shared`` 而非某个业务模块内：工单创建、草稿发布、
操作申请与审批决策都依赖同一套语义。

并发安全由 ``(scope, key)`` 唯一约束保证，而不是应用层的「先查后写」——
见 AGENTS.md §6。冲突情形分三类：

* 键不存在            → 首次执行；先以 ``in_progress`` 占位
* 键存在且请求哈希相同 → 重放首次结果
* 键存在且请求哈希不同 → ``409 idempotency_key_reused``
* 键存在但仍在执行中   → ``409 idempotency_key_in_progress``
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from supportflow.shared.db import Base
from supportflow.shared.errors import AppError, IdempotencyKeyReused

IN_PROGRESS = "in_progress"
COMPLETED = "completed"


class IdempotencyKeyInProgress(AppError):
    status = 409
    code = "idempotency_key_in_progress"
    title = "相同幂等键的请求正在处理中"


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("scope", "key", name="uq_idempotency_scope_key"),
        # 过期记录清理任务按 expires_at 扫描，避免全表扫。
        Index("ix_idempotency_records_expires_at", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    scope: Mapped[str] = mapped_column(String(64))
    key: Mapped[str] = mapped_column(String(200))
    request_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


@dataclass(frozen=True, slots=True)
class ReplayedResponse:
    status_code: int
    body: dict[str, Any]


class IdempotencyPort(Protocol):
    """写用例依赖的最小契约。放在 ``shared`` 是因为它是跨模块关注点。

    调用方与服务实现共用**同一个请求级事务**：因此「占位后失败」会随事务回滚
    一并消失，幂等键不会被一次失败请求永久占死。
    """

    def reserve(self, scope: str, key: str, request_hash: str) -> ReplayedResponse | None:
        """占位或返回重放结果；``None`` 表示应继续执行首次逻辑。"""
        ...

    def complete(
        self, scope: str, key: str, *, status_code: int, body: dict[str, Any]
    ) -> None: ...


def fingerprint(payload: Any) -> str:
    """请求指纹：对规范化 JSON 取 SHA-256，用于区分同键不同请求。"""
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class IdempotencyStore:
    def __init__(self, session: Session, *, ttl_seconds: int = 24 * 3600) -> None:
        self._session = session
        self._ttl = ttl_seconds

    def reserve(self, scope: str, key: str, request_hash: str) -> ReplayedResponse | None:
        """占位或返回重放结果。返回 ``None`` 表示调用方应继续执行首次逻辑。"""
        now = datetime.now(UTC)
        existing = self._find(scope, key)
        if existing is not None:
            if existing.expires_at > now:
                return self._resolve(existing, request_hash)
            # 已过期：复用该行（受唯一约束限制不能插入新行），视为首次执行。
            existing.request_hash = request_hash
            existing.status = IN_PROGRESS
            existing.status_code = None
            existing.response_body = None
            existing.created_at = now
            existing.expires_at = now + timedelta(seconds=self._ttl)
            self._session.flush()
            return None

        record = IdempotencyRecord(
            scope=scope,
            key=key,
            request_hash=request_hash,
            status=IN_PROGRESS,
            expires_at=now + timedelta(seconds=self._ttl),
        )
        try:
            # 保存点：唯一约束冲突不应终止外层事务。
            with self._session.begin_nested():
                self._session.add(record)
                self._session.flush()
        except IntegrityError:
            concurrent = self._find(scope, key)
            if concurrent is None:  # pragma: no cover - 约束冲突后必然可见
                raise
            return self._resolve(concurrent, request_hash)
        return None

    def complete(
        self, scope: str, key: str, *, status_code: int, body: dict[str, Any]
    ) -> None:
        record = self._find(scope, key)
        if record is None:  # pragma: no cover - 占位成功后才可能调用
            raise RuntimeError(f"幂等记录缺失: scope={scope} key={key}")
        record.status = COMPLETED
        record.status_code = status_code
        record.response_body = body

    def _find(self, scope: str, key: str) -> IdempotencyRecord | None:
        stmt = select(IdempotencyRecord).where(
            IdempotencyRecord.scope == scope, IdempotencyRecord.key == key
        )
        return self._session.scalars(stmt).one_or_none()

    def _resolve(
        self, record: IdempotencyRecord, request_hash: str
    ) -> ReplayedResponse | None:
        if record.request_hash != request_hash:
            raise IdempotencyKeyReused(
                "该幂等键已用于内容不同的请求", scope=record.scope, key=record.key
            )
        if record.status == IN_PROGRESS:
            raise IdempotencyKeyInProgress("相同幂等键的请求正在处理中，请稍后重试")
        return ReplayedResponse(
            status_code=record.status_code or 200, body=record.response_body or {}
        )
