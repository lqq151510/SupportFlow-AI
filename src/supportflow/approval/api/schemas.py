"""审批接口的请求/响应契约。

响应里**不包含**任何客户原文：`reason` 是模型提议时写下的不可变理由，
`quote_text` 之类的证据字段不在这里出现（AGENTS.md §8：客户侧响应不携带内部引用）。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from supportflow.approval.domain.models import (
    ActionDecision,
    ActionLedgerEntry,
    ActionRequest,
)


class ActionRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticket_id: UUID
    run_id: UUID
    action_type: str
    status: str
    reason: str
    ticket_version: int
    target_assignee_id: UUID | None
    created_at: datetime
    expires_at: datetime
    decided_at: datetime | None
    decided_by: UUID | None
    version: int

    @classmethod
    def of(cls, request: ActionRequest) -> ActionRequestOut:
        return cls(
            id=request.id,
            ticket_id=request.ticket_id,
            run_id=request.run_id,
            action_type=request.action_type.value,
            status=request.status.value,
            reason=str(request.parameters.get("reason", "")),
            ticket_version=request.ticket_version,
            target_assignee_id=request.target_assignee_id,
            created_at=request.created_at,
            expires_at=request.expires_at,
            decided_at=request.decided_at,
            decided_by=request.decided_by,
            version=request.version,
        )


class ActionRequestListOut(BaseModel):
    items: list[ActionRequestOut]


class ActionLedgerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    action_request_id: UUID
    idempotency_key: str
    ticket_id: UUID
    action_type: str
    result: dict[str, object]
    executed_at: datetime

    @classmethod
    def of(cls, entry: ActionLedgerEntry) -> ActionLedgerOut:
        return cls(
            id=entry.id,
            action_request_id=entry.action_request_id,
            idempotency_key=entry.idempotency_key,
            ticket_id=entry.ticket_id,
            action_type=entry.action_type.value,
            result=dict(entry.result),
            executed_at=entry.executed_at,
        )


class ActionDecisionIn(BaseModel):
    approve: bool = Field(description="true=批准并执行；false=拒绝")


class ActionDecisionOut(BaseModel):
    """决策结果。

    ``executed=False`` 且 ``blocked_reason="rejected"`` 表示**这是一次成功的拒绝**，
    不是错误；过期的申请会在决策时抛出 ``action_request_expired``（409）。
    """

    request: ActionRequestOut
    executed: bool
    blocked_reason: str | None
    ledger: ActionLedgerOut | None

    @classmethod
    def of(cls, decision: ActionDecision) -> ActionDecisionOut:
        return cls(
            request=ActionRequestOut.of(decision.request),
            executed=decision.executed,
            blocked_reason=decision.blocked_reason,
            ledger=ActionLedgerOut.of(decision.ledger_entry) if decision.ledger_entry else None,
        )
