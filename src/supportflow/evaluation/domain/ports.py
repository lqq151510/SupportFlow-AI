"""评测域端口。

评测模块**不直接**调用模型或知识库：分类、检索与语料导入都经端口由组合根适配，
因此评测与 agent / knowledge / model 三个模块保持单向依赖（AGENTS.md §3）。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from supportflow.evaluation.domain.models import (
    EvaluationCase,
    EvaluationRun,
    FrozenCase,
    FrozenCorpusDoc,
    RetrievedEvidence,
)
from supportflow.identity.domain.models import Principal


class EvaluationCaseRepositoryPort(Protocol):
    def replace_all(self, cases: Sequence[FrozenCase]) -> tuple[int, int]:
        """以冻结集为准整体导入：已存在的复用，缺失的新建。返回 ``(新建, 复用)``。"""
        ...

    def list_enabled(self) -> list[EvaluationCase]: ...

    def count(self) -> int: ...


class EvaluationRunRepositoryPort(Protocol):
    def start(
        self, *, index_version: str, mode: str, model_config_id: UUID | None
    ) -> EvaluationRun: ...

    def record(
        self,
        run_id: UUID,
        case_id: UUID,
        *,
        category_correct: bool | None,
        recall_at_5: bool | None,
        detail: dict[str, object],
    ) -> None: ...

    def finish(
        self,
        run_id: UUID,
        *,
        status: str,
        metrics: dict[str, object] | None,
        error_code: str | None = None,
    ) -> EvaluationRun: ...

    def find_by_id(self, run_id: UUID) -> EvaluationRun | None: ...

    def list_results(self, run_id: UUID) -> list[dict[str, object]]: ...


class CorpusSeedPort(Protocol):
    """把冻结语料导入知识库（幂等：同标题同内容不重复导入）。

    语料导入走知识模块的导入用例，需要管理员身份。
    """

    def seed(
        self, principal: Principal, docs: Sequence[FrozenCorpusDoc]
    ) -> int: ...


class ClassifyPort(Protocol):
    """分类能力（真实模式走聊天网关，Mock 走确定性实现）。"""

    def classify(
        self, *, subject: str, body: str, mode: str
    ) -> tuple[str | None, float]: ...


class RetrievePort(Protocol):
    """检索能力（走当前索引版本的检索路线）。"""

    def retrieve(self, query: str, *, limit: int = 5) -> list[RetrievedEvidence]: ...
