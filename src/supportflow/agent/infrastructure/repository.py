"""agent 模块的持久化实现。"""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from supportflow.agent.domain.models import (
    AgentRun,
    RunEvent,
    RunEventType,
    RunStatus,
    RunStepRecord,
)
from supportflow.agent.infrastructure.tables import (
    RUN_EVENT_ID_SEQUENCE,
    AgentRunRow,
    RunEventRow,
    RunStepRow,
)
from supportflow.shared.clock import utcnow
from supportflow.shared.errors import RunAlreadyActive


def _to_run(row: AgentRunRow) -> AgentRun:
    return AgentRun(
        id=row.id,
        ticket_id=row.ticket_id,
        status=RunStatus(row.status),
        model_mode=row.model_mode,
        chat_model_name=row.chat_model_name,
        error_code=row.error_code,
        step_count=row.step_count,
        tool_call_count=row.tool_call_count,
        lease_owner=row.lease_owner,
        lease_expires_at=row.lease_expires_at,
        retry_of_run_id=row.retry_of_run_id,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


class SqlAlchemyRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self, *, ticket_id: UUID, model_mode: str, retry_of_run_id: UUID | None = None
    ) -> AgentRun:
        row = AgentRunRow(
            ticket_id=ticket_id,
            status=RunStatus.QUEUED.value,
            model_mode=model_mode,
            retry_of_run_id=retry_of_run_id,
        )
        try:
            # 保存点：部分唯一索引冲突不应终止外层事务（工单创建与运行创建同事务）。
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except IntegrityError as exc:
            raise RunAlreadyActive("该工单已有活动中的运行") from exc
        return _to_run(row)

    def find_by_id(self, run_id: UUID) -> AgentRun | None:
        row = self._session.get(AgentRunRow, run_id)
        return _to_run(row) if row else None

    def list_for_ticket(self, ticket_id: UUID) -> list[AgentRun]:
        rows = self._session.scalars(
            select(AgentRunRow)
            .where(AgentRunRow.ticket_id == ticket_id)
            .order_by(AgentRunRow.created_at, AgentRunRow.id)
        ).all()
        return [_to_run(row) for row in rows]

    def claim(self, run_id: UUID, *, owner: str, lease_seconds: int) -> AgentRun | None:
        row = self._session.scalars(
            select(AgentRunRow).where(AgentRunRow.id == run_id).with_for_update()
        ).one_or_none()
        if row is None or not self._is_claimable(row):
            return None
        self._mark_running(row, owner=owner, lease_seconds=lease_seconds)
        return _to_run(row)

    def claim_next(self, *, owner: str, lease_seconds: int) -> AgentRun | None:
        """领取最早的待执行运行。

        使用 ``FOR UPDATE SKIP LOCKED``：多个 Worker 并发时各自领到不同的行，
        不需要外部队列，也不会互相阻塞。
        """
        stmt = (
            select(AgentRunRow)
            .where(
                (AgentRunRow.status == RunStatus.QUEUED.value)
                | (
                    (AgentRunRow.status == RunStatus.RUNNING.value)
                    & (AgentRunRow.lease_expires_at < utcnow())
                )
            )
            .order_by(AgentRunRow.created_at, AgentRunRow.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        row = self._session.scalars(stmt).one_or_none()
        if row is None:
            return None
        self._mark_running(row, owner=owner, lease_seconds=lease_seconds)
        return _to_run(row)

    def finish(
        self,
        run_id: UUID,
        *,
        status: RunStatus,
        error_code: str | None = None,
        chat_model_name: str | None = None,
    ) -> None:
        values: dict[str, object] = {
            "status": status.value,
            "finished_at": utcnow(),
            "error_code": error_code,
            "lease_owner": None,
            "lease_expires_at": None,
        }
        if chat_model_name is not None:
            values["chat_model_name"] = chat_model_name
        self._session.execute(
            update(AgentRunRow).where(AgentRunRow.id == run_id).values(**values)
        )

    def bump_counters(self, run_id: UUID, *, steps: int = 0, tool_calls: int = 0) -> None:
        if not steps and not tool_calls:
            return
        self._session.execute(
            update(AgentRunRow)
            .where(AgentRunRow.id == run_id)
            .values(
                step_count=AgentRunRow.step_count + steps,
                tool_call_count=AgentRunRow.tool_call_count + tool_calls,
            )
        )

    @staticmethod
    def _is_claimable(row: AgentRunRow) -> bool:
        if row.status == RunStatus.QUEUED.value:
            return True
        if row.status != RunStatus.RUNNING.value:
            return False
        return row.lease_expires_at is None or row.lease_expires_at < utcnow()

    @staticmethod
    def _mark_running(row: AgentRunRow, *, owner: str, lease_seconds: int) -> None:
        row.status = RunStatus.RUNNING.value
        row.lease_owner = owner
        row.lease_expires_at = utcnow() + timedelta(seconds=lease_seconds)
        if row.started_at is None:
            row.started_at = utcnow()


class SqlAlchemyRunEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(
        self, run_id: UUID, event_type: RunEventType, payload: dict[str, object]
    ) -> int:
        event_id = int(self._session.scalar(select(RUN_EVENT_ID_SEQUENCE.next_value())) or 0)
        self._session.add(
            RunEventRow(
                id=event_id,
                run_id=run_id,
                event_type=event_type.value,
                payload=payload,
            )
        )
        self._session.flush()
        return event_id

    def list_since(self, run_id: UUID, *, after_id: int, limit: int) -> list[RunEvent]:
        rows = self._session.scalars(
            select(RunEventRow)
            .where(RunEventRow.run_id == run_id, RunEventRow.id > after_id)
            .order_by(RunEventRow.id)
            .limit(limit)
        ).all()
        return [
            RunEvent(
                id=row.id,
                run_id=row.run_id,
                event_type=RunEventType(row.event_type),
                payload=dict(row.payload or {}),
                created_at=row.created_at,
            )
            for row in rows
        ]


class SqlAlchemyRunStepRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, run_id: UUID, step: RunStepRecord) -> None:
        self._session.add(
            RunStepRow(
                run_id=run_id,
                step_no=step.step_no,
                node_name=step.node_name,
                latency_ms=step.latency_ms,
                detail=step.detail,
            )
        )
        self._session.flush()

    def list_steps(self, run_id: UUID) -> list[RunStepRecord]:
        rows = self._session.scalars(
            select(RunStepRow)
            .where(RunStepRow.run_id == run_id)
            .order_by(RunStepRow.step_no)
        ).all()
        return [
            RunStepRecord(
                step_no=row.step_no,
                node_name=row.node_name,
                latency_ms=row.latency_ms,
                detail=row.detail,
            )
            for row in rows
        ]
