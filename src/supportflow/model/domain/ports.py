"""模型接入域的端口。

`SecretCipherPort` 把「怎么加密」挡在基础设施层之外：应用服务只知道
「给明文、拿密文」，以及「给密文、拿明文」，因此将来轮换算法不必改动用例代码。
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from supportflow.model.domain.models import (
    ModelCapability,
    ModelConfig,
    ModelConfigUpdate,
    NewModelConfig,
)


class SecretCipherPort(Protocol):
    def encrypt(self, plaintext: str) -> str:
        """加密并返回可入库的密文串。主密钥缺失时应**直接失败**，不得静默存明文。"""
        ...

    def decrypt(self, ciphertext: str) -> str:
        """解密。密文被篡改或主密钥不对时应抛错，绝不返回可疑明文。"""
        ...


class ModelConfigRepositoryPort(Protocol):
    def add(self, config: NewModelConfig, *, ciphertext: str) -> ModelConfig: ...

    def find_by_id(self, config_id: UUID) -> ModelConfig | None: ...

    def list_all(self) -> list[ModelConfig]: ...

    def find_enabled(self, capability: ModelCapability) -> ModelConfig | None: ...

    def update(
        self, config_id: UUID, changes: ModelConfigUpdate, *, ciphertext: str | None
    ) -> ModelConfig:
        """按 ``changes`` 更新；``ciphertext`` 为 ``None`` 表示保持原密钥。"""
        ...

    def enable(self, config_id: UUID) -> ModelConfig:
        """启用该配置，并在同一事务内停用同类能力的其他配置。"""
        ...

    def ciphertext_of(self, config_id: UUID) -> str | None:
        """取密文本身。仅供运行期解密与连接测试使用，**不得**出现在任何响应里。"""
        ...
