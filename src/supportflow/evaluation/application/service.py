"""评测用例编排：导入冻结集、执行评测并聚合指标。

两段式指标（PLAN 验收目标：分类准确率 ≥90%、Recall@5 ≥80%、安全转人工 100%）：

- ``category_correct``：分类是否与期望一致；
- ``recall_at_5``：期望来源是否出现在 Top-5 检索证据里；
- ``handoff_correct``：安全闸的处置是否与期望一致（安全场景应被拦截，
  正常场景不应被误拦）。守卫是确定性规则，与模式（mock/real）无关。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from uuid import UUID

from supportflow.evaluation.domain.models import (
    CaseJudgement,
    EvaluationCase,
    EvaluationMetrics,
    EvaluationRun,
    FrozenSet,
    ImportSummary,
)
from supportflow.evaluation.domain.ports import (
    ClassifyPort,
    CorpusSeedPort,
    EvaluationCaseRepositoryPort,
    EvaluationRunRepositoryPort,
    RetrievePort,
    SecurityGuardPort,
)
from supportflow.identity.domain.models import Principal
from supportflow.shared.errors import Forbidden

logger = logging.getLogger(__name__)


class EvaluationService:
    def __init__(
        self,
        cases: EvaluationCaseRepositoryPort,
        runs: EvaluationRunRepositoryPort,
        corpus: CorpusSeedPort,
        classify: ClassifyPort,
        retrieve: RetrievePort,
        guard: SecurityGuardPort,
        *,
        index_version_provider: Callable[[], str],
    ) -> None:
        self._cases = cases
        self._runs = runs
        self._corpus = corpus
        self._classify = classify
        self._retrieve = retrieve
        self._guard = guard
        self._index_version = index_version_provider

    # --- 导入 ---------------------------------------------------------------

    def import_frozen(self, principal: Principal, frozen: FrozenSet) -> ImportSummary:
        """导入冻结用例与语料。语料导入幂等（同标题同内容不重复）。"""
        self._require_admin(principal)
        corpus_docs = self._corpus.seed(principal, frozen.corpus)
        created, reused = self._cases.replace_all(frozen.cases)
        summary = ImportSummary(created=created, reused=reused, corpus_docs=corpus_docs)
        logger.info("冻结评测集导入: %s", summary)
        return summary

    def count_cases(self) -> int:
        return self._cases.count()

    # --- 执行 ---------------------------------------------------------------

    def run_evaluation(
        self,
        principal: Principal,
        *,
        mode: str,
        limit: int | None = None,
    ) -> EvaluationRun:
        """执行一次评测并落库指标。**只读知识库**，不创建工单或运行。"""
        self._require_admin(principal)

        cases = self._cases.list_enabled()
        if limit is not None:
            cases = cases[:limit]
        if not cases:
            raise ValueError("没有可用的评测用例，请先导入冻结集")

        run = self._runs.start(
            index_version=self._index_version(), mode=mode, model_config_id=None
        )
        # mode 必须从**本次调用**传到分类点：这是本仓库第三次踩
        # 「参数存在但没传到使用点」的坑（S3 执行器同款），因此不做任何默认值兜底。
        judgements = [self._judge(run.id, case, mode=mode) for case in cases]
        metrics = self._aggregate(len(cases), judgements)
        return self._runs.finish(run.id, status="COMPLETED", metrics=metrics.as_dict())

    # --- 查询与报告 ---------------------------------------------------------

    def get_run(self, principal: Principal, run_id: UUID) -> EvaluationRun:
        self._require_admin(principal)
        run = self._runs.find_by_id(run_id)
        if run is None:
            from supportflow.shared.errors import NotFound

            raise NotFound("评测运行不存在")
        return run

    def export_report(self, principal: Principal, run_id: UUID) -> dict[str, object]:
        """导出 JSON 报告：聚合指标 + 逐用例结果（PLAN §6）。"""
        run = self.get_run(principal, run_id)
        return {
            "run": {
                "id": str(run.id),
                "mode": run.mode,
                "index_version": run.index_version,
                "status": run.status,
                "started_at": run.started_at.isoformat(),
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            },
            "metrics": run.metrics,
            "results": self._runs.list_results(run_id),
        }

    # --- 内部 ---------------------------------------------------------------

    def _judge(self, run_id: UUID, case: EvaluationCase, *, mode: str) -> CaseJudgement:
        expected_category = case.expected_ticket_category
        category_correct: bool | None = None
        classified: str | None = None
        if expected_category is not None:
            classified, _confidence = self._classify.classify(
                subject=case.subject, body=case.question, mode=mode
            )
            category_correct = classified == expected_category

        recall_at_5: bool | None = None
        evidence_titles: list[str | None] = []
        if case.expected_source_ids:
            evidence = self._retrieve.retrieve(case.question, limit=5)
            evidence_titles = [item.source_title for item in evidence]
            top5 = evidence_titles[:5]
            recall_at_5 = any(expected in top5 for expected in case.expected_source_ids)

        # 安全闸考核：守卫是确定性规则，对所有用例都判 —— 正常用例被误拦同样算失败。
        handoff_rule = self._guard.inspect(subject=case.subject, body=case.question)
        handoff_triggered = handoff_rule is not None
        handoff_correct = handoff_triggered == case.expect_handoff

        self._runs.record(
            run_id,
            case.id,
            category_correct=category_correct,
            recall_at_5=recall_at_5,
            handoff_correct=handoff_correct,
            detail={
                "classified_category": classified,
                "expected_category": expected_category,
                "expected_source_ids": case.expected_source_ids,
                "evidence_titles": evidence_titles,
                "expect_handoff": case.expect_handoff,
                "handoff_triggered": handoff_triggered,
                "handoff_rule": handoff_rule,
            },
        )
        return CaseJudgement(
            case_id=case.id,
            case_key=case.case_key,
            category=case.category,
            category_correct=category_correct,
            recall_at_5=recall_at_5,
            handoff_correct=handoff_correct,
            detail={
                "classified": classified,
                "expected": expected_category,
                "recall": recall_at_5,
                "handoff_rule": handoff_rule,
            },
        )

    @staticmethod
    def _aggregate(total: int, judgements: list[CaseJudgement]) -> EvaluationMetrics:
        category_results = [
            j.category_correct for j in judgements if j.category_correct is not None
        ]
        recall_results = [j.recall_at_5 for j in judgements if j.recall_at_5 is not None]
        handoff_results = [
            j.handoff_correct for j in judgements if j.handoff_correct is not None
        ]
        category_correct = sum(1 for v in category_results if v)
        recall_hits = sum(1 for v in recall_results if v)
        handoff_hits = sum(1 for v in handoff_results if v)
        return EvaluationMetrics(
            total_cases=total,
            category_total=len(category_results),
            category_correct=category_correct,
            category_accuracy=(
                category_correct / len(category_results) if category_results else 0.0
            ),
            recall_total=len(recall_results),
            recall_hits=recall_hits,
            recall_at_5=recall_hits / len(recall_results) if recall_results else 0.0,
            handoff_total=len(handoff_results),
            handoff_correct=handoff_hits,
            handoff_accuracy=(
                handoff_hits / len(handoff_results) if handoff_results else 0.0
            ),
        )

    @staticmethod
    def _require_admin(principal: Principal) -> None:
        """评测是管理员能力（PLAN §3：管理员另加评测）。"""
        if not principal.is_admin:
            raise Forbidden("仅管理员可以执行评测")
