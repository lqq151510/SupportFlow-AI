"""模型配置接口的请求与响应契约。

**响应里永远没有密钥字段** —— 只有 ``api_key_configured`` 这一个布尔事实。
这是 AGENTS.md §4「查询接口只返回密钥是否已配置，永不回显明文」的落地点，
因此这里不是靠序列化时排除，而是类型层面就不存在该字段。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from supportflow.model.domain.models import (
    ConnectionTestResult,
    ModelCapability,
    ModelConfig,
    ModelProtocol,
)


class ModelConfigCreateIn(BaseModel):
    capability: ModelCapability
    protocol: ModelProtocol = ModelProtocol.OPENAI_COMPATIBLE
    base_url: str = Field(min_length=1, max_length=500)
    model_name: str = Field(min_length=1, max_length=200)
    #: 明文密钥。只在请求体内出现一次，服务端立即加密，绝不回显、绝不落库。
    api_key: str = Field(min_length=1, max_length=500)
    embedding_dim: int | None = Field(default=None, ge=1, le=8192)


class ModelConfigUpdateIn(BaseModel):
    """局部更新。``api_key`` 省略表示保持原密钥不变。"""

    base_url: str | None = Field(default=None, min_length=1, max_length=500)
    model_name: str | None = Field(default=None, min_length=1, max_length=200)
    api_key: str | None = Field(default=None, min_length=1, max_length=500)
    embedding_dim: int | None = Field(default=None, ge=1, le=8192)


class ModelConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    capability: ModelCapability
    protocol: ModelProtocol
    base_url: str
    model_name: str
    api_key_configured: bool
    embedding_dim: int | None
    enabled: bool
    version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, config: ModelConfig) -> ModelConfigOut:
        return cls.model_validate(config)


class ModelConfigListOut(BaseModel):
    items: list[ModelConfigOut]


class ConnectionTestOut(BaseModel):
    ok: bool
    latency_ms: int
    model_name: str
    error_code: str | None = None
    detail: str | None = None

    @classmethod
    def of(cls, result: ConnectionTestResult) -> ConnectionTestOut:
        return cls(
            ok=result.ok,
            latency_ms=result.latency_ms,
            model_name=result.model_name,
            error_code=result.error_code,
            detail=result.detail,
        )
