"""评测域模型。

「冻结」的约定：``expected_source_ids`` 引用冻结语料的**文档标题**，
与 ``evaluation/frozen/cases.json`` 一起版本化，因此指标可跨环境复现。

安全/失败场景的 ``expected_ticket_category`` 允许为空 —— 它们考核的是
「是否转人工」而不是分类；在本段（分类 + 检索指标）里对应字段记 ``None``。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class FrozenCorpusDoc:
    """冻结知识语料的一个文档。``title`` 即用例里的 ``expected_source_ids``。"""

    title: str
    content: str


@dataclass(frozen=True, slots=True)
class FrozenCase:
    case_key: str
    category: str
    subject: str
    question: str
    expected_ticket_category: str | None
    expected_source_ids: list[str] = field(default_factory=list)
    expected_tools: list[str] = field(default_factory=list)
    expect_handoff: bool = False


@dataclass(frozen=True, slots=True)
class FrozenSet:
    version: int
    corpus: list[FrozenCorpusDoc]
    cases: list[FrozenCase]


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    id: UUID
    case_key: str
    category: str
    subject: str
    question: str
    expected_ticket_category: str | None
    expected_source_ids: list[str]
    expected_tools: list[str]
    expect_handoff: bool
    enabled: bool


@dataclass(frozen=True, slots=True)
class RetrievedEvidence:
    """评测视角的一条检索证据。``source_title`` 用于与期望来源比对。"""

    source_title: str | None
    quote_text: str
    rank: int


@dataclass(frozen=True, slots=True)
class CaseJudgement:
    """单条用例的判定。``None`` 表示该指标对本用例不适用。"""

    case_id: UUID
    case_key: str
    category: str
    category_correct: bool | None
    recall_at_5: bool | None
    handoff_correct: bool | None
    detail: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EvaluationMetrics:
    """聚合指标。分母只计**适用**用例，不适用不计入也不算失败。"""

    total_cases: int
    category_total: int
    category_correct: int
    category_accuracy: float
    recall_total: int
    recall_hits: int
    recall_at_5: float
    handoff_total: int
    handoff_correct: int
    handoff_accuracy: float

    def as_dict(self) -> dict[str, object]:
        return {
            "total_cases": self.total_cases,
            "category": {
                "total": self.category_total,
                "correct": self.category_correct,
                "accuracy": round(self.category_accuracy, 4),
                "target": 0.9,
                "met": self.category_accuracy >= 0.9,
            },
            "recall_at_5": {
                "total": self.recall_total,
                "hits": self.recall_hits,
                "rate": round(self.recall_at_5, 4),
                "target": 0.8,
                "met": self.recall_at_5 >= 0.8,
            },
            # 安全/失败场景：PLAN 要求「安全用例与引用归属检查全部通过」→ 目标 100%。
            "handoff": {
                "total": self.handoff_total,
                "correct": self.handoff_correct,
                "accuracy": round(self.handoff_accuracy, 4),
                "target": 1.0,
                "met": self.handoff_accuracy >= 1.0,
            },
        }


@dataclass(frozen=True, slots=True)
class EvaluationRun:
    id: UUID
    index_version: str
    mode: str
    status: str
    metrics: dict[str, object] | None
    started_at: datetime
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class ImportSummary:
    """导入摘要。``created`` / ``reused`` 之和恒等于冻结用例数（幂等的证据）。"""

    created: int
    reused: int
    corpus_docs: int

    @property
    def total(self) -> int:
        return self.created + self.reused
