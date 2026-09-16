"""评测接口。

全部端点**仅管理员**（PLAN §3：管理员另加评测）。
`POST /evaluations/import` 导入冻结集；`POST /evaluations/runs` 执行评测；
`GET /evaluations/runs/{id}/report` 导出 JSON 报告（PLAN §6）。
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from supportflow.bootstrap.container import Services
from supportflow.evaluation.api.schemas import (
    EvaluationImportOut,
    EvaluationRunCreateIn,
    EvaluationRunOut,
)
from supportflow.evaluation.frozen.loader import load_frozen_set
from supportflow.identity.api.dependencies import (
    csrf_protected_principal,
    current_principal,
    get_services,
)
from supportflow.identity.domain.models import Principal
from supportflow.shared.errors import InvalidRequest

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.post("/import", response_model=EvaluationImportOut)
def import_frozen_cases(
    principal: Principal = Depends(csrf_protected_principal),
    services: Services = Depends(get_services),
) -> EvaluationImportOut:
    """导入冻结评测集与语料（幂等）。"""
    summary = services.evaluations.import_frozen(principal, load_frozen_set())
    return EvaluationImportOut.of(summary)


@router.post("/runs", response_model=EvaluationRunOut, status_code=201)
def create_evaluation_run(
    payload: EvaluationRunCreateIn,
    principal: Principal = Depends(csrf_protected_principal),
    services: Services = Depends(get_services),
) -> EvaluationRunOut:
    """执行一次评测并落库指标。Mock 与真实模式的结果分别落库（AGENTS.md §10）。"""
    if payload.mode not in ("mock", "real"):
        raise InvalidRequest("mode 只能是 mock 或 real")
    run = services.evaluations.run_evaluation(
        principal, mode=payload.mode, limit=payload.limit
    )
    return EvaluationRunOut.of(run)


@router.get("/runs/{run_id}", response_model=EvaluationRunOut)
def get_evaluation_run(
    run_id: UUID,
    principal: Principal = Depends(current_principal),
    services: Services = Depends(get_services),
) -> EvaluationRunOut:
    return EvaluationRunOut.of(services.evaluations.get_run(principal, run_id))


@router.get("/runs/{run_id}/report")
def export_evaluation_report(
    run_id: UUID,
    principal: Principal = Depends(current_principal),
    services: Services = Depends(get_services),
) -> dict[str, object]:
    """导出 JSON 报告：聚合指标 + 逐用例结果。"""
    return services.evaluations.export_report(principal, run_id)
