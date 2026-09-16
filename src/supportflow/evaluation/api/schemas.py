"""评测接口的请求/响应契约。全部端点**仅管理员**（PLAN §3）。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from supportflow.evaluation.domain.models import EvaluationRun, ImportSummary


class EvaluationImportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    created: int
    reused: int
    corpus_docs: int

    @classmethod
    def of(cls, summary: ImportSummary) -> EvaluationImportOut:
        return cls(
            created=summary.created, reused=summary.reused, corpus_docs=summary.corpus_docs
        )


class EvaluationRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    index_version: str
    mode: str
    status: str
    metrics: dict[str, object] | None
    started_at: datetime
    finished_at: datetime | None

    @classmethod
    def of(cls, run: EvaluationRun) -> EvaluationRunOut:
        return cls(
            id=run.id,
            index_version=run.index_version,
            mode=run.mode,
            status=run.status,
            metrics=run.metrics,
            started_at=run.started_at,
            finished_at=run.finished_at,
        )


class EvaluationRunCreateIn(BaseModel):
    """执行一次评测。``mode`` 决定分类走 Mock 还是真实网关。"""

    mode: str = "mock"
    limit: int | None = None
