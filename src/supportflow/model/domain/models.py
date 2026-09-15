"""模型接入域的领域模型。

对齐 PLAN.md 核心表 #17 与 AGENTS.md §4：

- API Key **只保存 AES-GCM 密文**，查询接口只回答「是否已配置」；
- 主密钥只来自 ``MODEL_SECRET_MASTER_KEY`` 环境变量，永不进入源码与提交历史；
- 单工作区每类能力只启用一个配置 —— 由 ``model_configs`` 上的部分唯一索引兜底，
  应用层不做「先查后写」判重。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ModelCapability(StrEnum):
    """聊天与 Embedding **分别配置**（PLAN.md §3）。"""

    CHAT = "CHAT"
    EMBEDDING = "EMBEDDING"


class ModelProtocol(StrEnum):
    """首版只支持 OpenAI-compatible 协议。"""

    OPENAI_COMPATIBLE = "OPENAI_COMPATIBLE"


@dataclass(frozen=True, slots=True)
class ModelConfig:
    """配置的**只读视图**。刻意不含明文 Key —— 领域模型里就没有这个字段。"""

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


@dataclass(frozen=True, slots=True)
class NewModelConfig:
    """待创建的配置。

    **刻意不含 ``api_key`` 字段**：明文 Key 不能进入领域对象，它由应用服务加密后
    以 ``ciphertext`` 形式单独传给仓储，从而让「明文不落库」成为类型层面的约束。
    """

    capability: ModelCapability
    protocol: ModelProtocol
    base_url: str
    model_name: str
    embedding_dim: int | None = None


@dataclass(frozen=True, slots=True)
class ModelConfigUpdate:
    """局部更新。``api_key`` 为 ``None`` 表示保持原密钥不变。"""

    base_url: str | None = None
    model_name: str | None = None
    api_key: str | None = None
    embedding_dim: int | None = None


@dataclass(frozen=True, slots=True)
class ConnectionTestResult:
    """连接测试结果。**不含任何密钥片段**，只给出可诊断的结构化信息。"""

    ok: bool
    latency_ms: int
    model_name: str
    error_code: str | None = None
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class ResolvedEmbeddingConfig:
    """运行期构造 Embedding 网关所需的**解密后**配置。只存在于进程内存中。

    ``embedding_dim`` 是**配置声明的**维度；调用方必须把它与实际返回的向量长度对照，
    不一致即配置错误（索引版本按维度与模型界定）。
    """

    base_url: str
    model_name: str
    api_key: str
    timeout_seconds: float
    embedding_dim: int


@dataclass(frozen=True, slots=True)
class ResolvedChatConfig:
    """运行期构造真实网关所需的**解密后**配置。只存在于进程内存中。"""

    base_url: str
    model_name: str
    api_key: str
    timeout_seconds: float
    max_attempts: int
