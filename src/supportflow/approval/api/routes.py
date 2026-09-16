"""操作申请（审批）接口。

全部端点**仅坐席与管理员**（PLAN §5）；写操作必须携带 CSRF 与 `Idempotency-Key`。

幂等语义（AGENTS.md §6）：审批决策**不可重复** —— 同一申请第二次决策返回
``409 action_request_not_pending``，而不是重放首次结果。原因是决策不是"创建"而是
"状态迁移"：账本上的 ``action_request_id`` 唯一约束保证动作至多执行一次，
因此重复请求只会得到"已被处理"的明确答复。
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header

from supportflow.approval.api.schemas import (
    ActionDecisionIn,
    ActionDecisionOut,
    ActionRequestListOut,
    ActionRequestOut,
)
from supportflow.bootstrap.container import Services
from supportflow.identity.api.dependencies import (
    csrf_protected_principal,
    current_principal,
    get_services,
)
from supportflow.identity.domain.models import Principal
from supportflow.shared.errors import InvalidRequest

router = APIRouter(prefix="/action-requests", tags=["action-requests"])


@router.get("", response_model=ActionRequestListOut)
def list_action_requests(
    status: str = "PENDING",
    limit: int = 50,
    principal: Principal = Depends(current_principal),
    services: Services = Depends(get_services),
) -> ActionRequestListOut:
    """按状态列出操作申请。默认列出待审批。"""
    if limit < 1 or limit > 100:
        raise InvalidRequest("limit 必须在 1..100 之间")
    requests = services.approvals.list_by_status_value(principal, status, limit=limit)
    return ActionRequestListOut(items=[ActionRequestOut.of(item) for item in requests])


@router.get("/{request_id}", response_model=ActionRequestOut)
def get_action_request(
    request_id: UUID,
    principal: Principal = Depends(current_principal),
    services: Services = Depends(get_services),
) -> ActionRequestOut:
    return ActionRequestOut.of(services.approvals.get_request(principal, request_id))


@router.get("/{request_id}/ledger")
def get_action_ledger(
    request_id: UUID,
    principal: Principal = Depends(current_principal),
    services: Services = Depends(get_services),
) -> dict[str, object]:
    """查询该申请的执行记录。账本只追加，没有删除接口。"""
    services.approvals.get_request(principal, request_id)
    entry = services.approvals.find_ledger_entry(request_id)
    if entry is None:
        return {"executed": False, "ledger": None}
    from supportflow.approval.api.schemas import ActionLedgerOut

    return {"executed": True, "ledger": ActionLedgerOut.of(entry).model_dump(mode="json")}


@router.post("/{request_id}/decide", response_model=ActionDecisionOut)
def decide_action_request(
    request_id: UUID,
    payload: ActionDecisionIn,
    principal: Principal = Depends(csrf_protected_principal),
    services: Services = Depends(get_services),
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> ActionDecisionOut:
    """批准或拒绝。

    批准会**执行动作并写入账本**（同一事务），随后把运行推进到终态；
    拒绝只记录决策，不产生业务效果。
    """
    if not idempotency_key.strip():
        raise InvalidRequest("Idempotency-Key 不能为空")
    decision = services.approvals.decide(principal, request_id, approve=payload.approve)
    return ActionDecisionOut.of(decision)
