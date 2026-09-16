"""审批模块的持久化实现。

**不触碰工单表**：工单的读取与修改全走 ``TicketActionPort``（组合根适配），
因此这里只处理 ``action_requests`` 与 ``action_ledger`` 两张表。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from supportflow.approval.domain.models import (
    ActionLedgerEntry,
    ActionRequest,
    ActionRequestStatus,
    ActionType,
    NewActionRequest,
)
from supportflow.approval.infrastructure.tables import ActionLedgerRow, ActionRequestRow
from supportflow.shared.clock import utcnow
from supportflow.shared.errors import ActionRequestNotFound


def _to_request(row: ActionRequestRow) -> ActionRequest:
    return ActionRequest(
        id=row.id,
        ticket_id=row.ticket_id,
        run_id=row.run_id,
        action_type=ActionType(row.action_type),
        parameters=dict(row.parameters_json),
        ticket_version=row.ticket_version,
        target_assignee_id=row.target_assignee_id,
        status=ActionRequestStatus(row.status),
        created_at=row.created_at,
        expires_at=row.expires_at,
        decided_at=row.decided_at,
        decided_by=row.decided_by,
        version=row.version,
    )


def _to_entry(row: ActionLedgerRow) -> ActionLedgerEntry:
    return ActionLedgerEntry(
        id=row.id,
        action_request_id=row.action_request_id,
        idempotency_key=row.idempotency_key,
        ticket_id=row.ticket_id,
        action_type=ActionType(row.action_type),
        result=dict(row.result_json),
        executed_at=row.executed_at,
    )


class SqlAlchemyActionRequestRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, request: NewActionRequest, *, expires_at: datetime) -> ActionRequest:
        row = ActionRequestRow(
            ticket_id=request.ticket_id,
            run_id=request.run_id,
            action_type=request.action_type.value,
            parameters_json=request.parameters,
            ticket_version=request.ticket_version,
            target_assignee_id=request.target_assignee_id,
            status=ActionRequestStatus.PENDING.value,
            expires_at=expires_at,
        )
        self._session.add(row)
        self._session.flush()
        return _to_request(row)

    def find_by_id(self, request_id: UUID) -> ActionRequest | None:
        row = self._session.get(ActionRequestRow, request_id)
        return _to_request(row) if row else None

    def find_latest(self, run_id: UUID, action_type: ActionType) -> ActionRequest | None:
        row = self._session.scalars(
            select(ActionRequestRow)
            .where(
                ActionRequestRow.run_id == run_id,
                ActionRequestRow.action_type == action_type.value,
            )
            .order_by(ActionRequestRow.created_at.desc(), ActionRequestRow.id.desc())
            .limit(1)
        ).one_or_none()
        return _to_request(row) if row else None

    def find_pending(self, run_id: UUID, action_type: ActionType) -> ActionRequest | None:
        row = self._session.scalars(
            select(ActionRequestRow).where(
                ActionRequestRow.run_id == run_id,
                ActionRequestRow.action_type == action_type.value,
                ActionRequestRow.status == ActionRequestStatus.PENDING.value,
            )
        ).one_or_none()
        return _to_request(row) if row else None

    def list_by_run(self, run_id: UUID) -> list[ActionRequest]:
        rows = self._session.scalars(
            select(ActionRequestRow)
            .where(ActionRequestRow.run_id == run_id)
            .order_by(ActionRequestRow.created_at, ActionRequestRow.id)
        ).all()
        return [_to_request(row) for row in rows]

    def list_by_status(self, status: str, *, limit: int = 50) -> list[ActionRequest]:
        rows = self._session.scalars(
            select(ActionRequestRow)
            .where(ActionRequestRow.status == status)
            .order_by(ActionRequestRow.expires_at, ActionRequestRow.id)
            .limit(limit)
        ).all()
        return [_to_request(row) for row in rows]

    def claim_decision(
        self, request_id: UUID, *, approved: bool, decided_by: UUID, now: datetime
    ) -> ActionRequest | None:
        """条件更新：只有仍为 PENDING 时才迁移状态。

        返回 ``None`` 说明别人已经处理过（或已被标记过期）—— 调用方据此返回
        ``action_request_not_pending``，而不是继续执行动作。这比「先读后写」可靠：
        并发双审时两者都会读到 PENDING。
        """
        target = (
            ActionRequestStatus.APPROVED if approved else ActionRequestStatus.REJECTED
        ).value
        row = self._session.execute(
            update(ActionRequestRow)
            .where(
                ActionRequestRow.id == request_id,
                ActionRequestRow.status == ActionRequestStatus.PENDING.value,
            )
            .values(
                status=target,
                decided_at=now,
                decided_by=decided_by,
                version=ActionRequestRow.version + 1,
            )
            .returning(ActionRequestRow)
        ).one_or_none()
        if row is None:
            return None
        self._session.flush()
        return _to_request(row[0])

    def mark_expired(self, request_id: UUID, *, now: datetime) -> ActionRequest | None:
        row = self._session.execute(
            update(ActionRequestRow)
            .where(
                ActionRequestRow.id == request_id,
                ActionRequestRow.status == ActionRequestStatus.PENDING.value,
            )
            .values(status=ActionRequestStatus.EXPIRED.value, decided_at=now)
            .returning(ActionRequestRow)
        ).one_or_none()
        if row is None:
            return None
        self._session.flush()
        return _to_request(row[0])


class SqlAlchemyActionLedgerRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(
        self,
        *,
        action_request_id: UUID,
        idempotency_key: str,
        ticket_id: UUID,
        action_type: ActionType,
        result: dict[str, object],
    ) -> ActionLedgerEntry:
        row = ActionLedgerRow(
            action_request_id=action_request_id,
            idempotency_key=idempotency_key,
            ticket_id=ticket_id,
            action_type=action_type.value,
            result_json=result,
            executed_at=utcnow(),
        )
        self._session.add(row)
        self._session.flush()
        return _to_entry(row)

    def find_by_request(self, action_request_id: UUID) -> ActionLedgerEntry | None:
        row = self._session.scalars(
            select(ActionLedgerRow).where(
                ActionLedgerRow.action_request_id == action_request_id
            )
        ).one_or_none()
        return _to_entry(row) if row else None

    def require(self, action_request_id: UUID) -> ActionLedgerEntry:
        entry = self.find_by_request(action_request_id)
        if entry is None:
            raise ActionRequestNotFound("执行账本中没有该申请")
        return entry
