"""评测集 / 评测运行 / 评测结果的持久化实现。"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from supportflow.evaluation.domain.models import (
    EvaluationCase,
    EvaluationRun,
    FrozenCase,
)
from supportflow.evaluation.infrastructure.tables import (
    EvaluationCaseRow,
    EvaluationResultRow,
    EvaluationRunRow,
)
from supportflow.shared.clock import utcnow


def _to_case(row: EvaluationCaseRow) -> EvaluationCase:
    return EvaluationCase(
        id=row.id,
        case_key=row.case_key,
        category=row.category,
        subject=row.subject,
        question=row.question,
        expected_ticket_category=row.expected_ticket_category,
        expected_source_ids=[str(v) for v in (row.expected_source_ids or [])],
        expected_tools=[str(v) for v in (row.expected_tools or [])],
        expect_handoff=bool(row.expect_handoff),
        enabled=bool(row.enabled),
    )


def _to_run(row: EvaluationRunRow) -> EvaluationRun:
    return EvaluationRun(
        id=row.id,
        index_version=row.index_version,
        mode=row.mode,
        status=row.status,
        metrics=row.metrics_json,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


class SqlAlchemyEvaluationCaseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_all(self, cases: Sequence[FrozenCase]) -> tuple[int, int]:
        """按 ``case_key`` 幂等导入：已存在的复用（并同步内容），缺失的新建。"""
        existing = {
            row.case_key: row
            for row in self._session.scalars(select(EvaluationCaseRow)).all()
        }
        created = reused = 0
        for case in cases:
            row = existing.get(case.case_key)
            if row is None:
                self._session.add(
                    EvaluationCaseRow(
                        case_key=case.case_key,
                        category=case.category,
                        subject=case.subject,
                        question=case.question,
                        expected_ticket_category=case.expected_ticket_category,
                        expected_source_ids=list(case.expected_source_ids),
                        expected_tools=list(case.expected_tools),
                        expect_handoff=case.expect_handoff,
                        enabled=True,
                    )
                )
                created += 1
                continue
            # 冻结集更新后同步内容：用例是版本化资产，库里的必须与冻结文件一致。
            row.category = case.category
            row.subject = case.subject
            row.question = case.question
            row.expected_ticket_category = case.expected_ticket_category
            row.expected_source_ids = list(case.expected_source_ids)
            row.expected_tools = list(case.expected_tools)
            row.expect_handoff = case.expect_handoff
            reused += 1
        self._session.flush()
        return created, reused

    def list_enabled(self) -> list[EvaluationCase]:
        rows = self._session.scalars(
            select(EvaluationCaseRow)
            .where(EvaluationCaseRow.enabled.is_(True))
            .order_by(EvaluationCaseRow.case_key)
        ).all()
        return [_to_case(row) for row in rows]

    def count(self) -> int:
        return int(self._session.scalar(select(EvaluationCaseRow.id)) or 0) if False else len(
            self._session.scalars(select(EvaluationCaseRow.id)).all()
        )


class SqlAlchemyEvaluationRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def start(
        self, *, index_version: str, mode: str, model_config_id: UUID | None
    ) -> EvaluationRun:
        row = EvaluationRunRow(
            index_version=index_version,
            mode=mode,
            model_config_id=model_config_id,
            status="RUNNING",
        )
        self._session.add(row)
        self._session.flush()
        return _to_run(row)

    def record(
        self,
        run_id: UUID,
        case_id: UUID,
        *,
        category_correct: bool | None,
        recall_at_5: bool | None,
        detail: dict[str, object],
    ) -> None:
        self._session.add(
            EvaluationResultRow(
                run_id=run_id,
                case_id=case_id,
                category_correct=category_correct,
                recall_at_5=recall_at_5,
                detail_json=detail,
            )
        )
        self._session.flush()

    def finish(
        self,
        run_id: UUID,
        *,
        status: str,
        metrics: dict[str, object] | None,
        error_code: str | None = None,
    ) -> EvaluationRun:
        row = self._session.get(EvaluationRunRow, run_id)
        if row is None:  # pragma: no cover - start 刚创建
            raise ValueError(f"评测运行不存在: {run_id}")
        row.status = status
        row.metrics_json = metrics
        row.error_code = error_code
        row.finished_at = utcnow()
        self._session.flush()
        return _to_run(row)

    def find_by_id(self, run_id: UUID) -> EvaluationRun | None:
        row = self._session.get(EvaluationRunRow, run_id)
        return _to_run(row) if row else None

    def list_results(self, run_id: UUID) -> list[dict[str, object]]:
        """逐用例结果（连用例信息），供报告导出。"""
        rows = self._session.execute(
            select(EvaluationResultRow, EvaluationCaseRow)
            .join(EvaluationCaseRow, EvaluationCaseRow.id == EvaluationResultRow.case_id)
            .where(EvaluationResultRow.run_id == run_id)
            .order_by(EvaluationCaseRow.case_key)
        ).all()
        return [
            {
                "case_key": case.case_key,
                "category": case.category,
                "subject": case.subject,
                "question": case.question,
                "expected_ticket_category": case.expected_ticket_category,
                "expected_source_ids": list(case.expected_source_ids or []),
                "expect_handoff": bool(case.expect_handoff),
                "category_correct": result.category_correct,
                "recall_at_5": result.recall_at_5,
                "detail": dict(result.detail_json or {}),
            }
            for result, case in rows
        ]
