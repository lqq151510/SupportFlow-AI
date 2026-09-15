"""模型配置管理接口。

全部端点都是**管理员专用**（AGENTS.md §4），写操作必须通过 CSRF 校验。

连接测试是唯一会真正对外发起模型调用的端点：它用该配置的密钥做一次最小请求，
并校验 ``response_format=json`` 契约是否可用 —— 这一步能在接入真实模式前
把「模型不支持 JSON 模式」这类问题挡在配置阶段，而不是等到运行转人工才发现。
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from supportflow.bootstrap.container import Services
from supportflow.identity.api.dependencies import (
    csrf_protected_principal,
    current_principal,
    get_services,
)
from supportflow.identity.domain.models import Principal
from supportflow.model.api.schemas import (
    ConnectionTestOut,
    ModelConfigCreateIn,
    ModelConfigListOut,
    ModelConfigOut,
    ModelConfigUpdateIn,
)

router = APIRouter(prefix="/model-configs", tags=["model-configs"])


@router.get("", response_model=ModelConfigListOut)
def list_model_configs(
    principal: Principal = Depends(current_principal),
    services: Services = Depends(get_services),
) -> ModelConfigListOut:
    configs = services.model_configs.list_configs(principal)
    return ModelConfigListOut(items=[ModelConfigOut.of(config) for config in configs])


@router.post("", response_model=ModelConfigOut, status_code=201)
def create_model_config(
    payload: ModelConfigCreateIn,
    principal: Principal = Depends(csrf_protected_principal),
    services: Services = Depends(get_services),
) -> ModelConfigOut:
    config = services.model_configs.create(
        principal,
        capability=payload.capability,
        protocol=payload.protocol,
        base_url=payload.base_url,
        model_name=payload.model_name,
        api_key=payload.api_key,
        embedding_dim=payload.embedding_dim,
    )
    return ModelConfigOut.of(config)


@router.patch("/{config_id}", response_model=ModelConfigOut)
def update_model_config(
    config_id: UUID,
    payload: ModelConfigUpdateIn,
    principal: Principal = Depends(csrf_protected_principal),
    services: Services = Depends(get_services),
) -> ModelConfigOut:
    config = services.model_configs.update(
        principal,
        config_id,
        base_url=payload.base_url,
        model_name=payload.model_name,
        api_key=payload.api_key,
        embedding_dim=payload.embedding_dim,
    )
    return ModelConfigOut.of(config)


@router.post("/{config_id}/enable", response_model=ModelConfigOut)
def enable_model_config(
    config_id: UUID,
    principal: Principal = Depends(csrf_protected_principal),
    services: Services = Depends(get_services),
) -> ModelConfigOut:
    """启用该配置。同类能力的其他配置会在同一事务内被停用。"""
    config = services.model_configs.enable(principal, config_id)
    return ModelConfigOut.of(config)


@router.post("/{config_id}/test", response_model=ConnectionTestOut)
def test_model_config(
    config_id: UUID,
    principal: Principal = Depends(csrf_protected_principal),
    services: Services = Depends(get_services),
) -> ConnectionTestOut:
    result = services.model_configs.test_connection(principal, config_id)
    return ConnectionTestOut.of(result)
