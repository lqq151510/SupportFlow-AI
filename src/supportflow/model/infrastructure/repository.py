"""model 模块的持久化实现。

密钥在这个文件里**只以密文形式出入**：``add`` / ``update`` 接收调用方已加密的
``ciphertext``，``_to_config`` 组装领域模型时只记录「是否已配置」这一个布尔事实。
唯一能拿到密文的方法是 ``ciphertext_of``，它仅供运行期解密与连接测试使用。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from supportflow.model.domain.models import (
    ModelCapability,
    ModelConfig,
    ModelConfigUpdate,
    ModelProtocol,
    NewModelConfig,
)
from supportflow.model.infrastructure.tables import ModelConfigRow
from supportflow.shared.clock import utcnow
from supportflow.shared.errors import NotFound


def _to_config(row: ModelConfigRow) -> ModelConfig:
    return ModelConfig(
        id=row.id,
        capability=ModelCapability(row.capability),
        protocol=ModelProtocol(row.protocol),
        base_url=row.base_url,
        model_name=row.model_name,
        api_key_configured=bool(row.api_key_ciphertext),
        embedding_dim=row.embedding_dim,
        enabled=bool(row.enabled),
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyModelConfigRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, config: NewModelConfig, *, ciphertext: str) -> ModelConfig:
        row = ModelConfigRow(
            capability=config.capability.value,
            protocol=config.protocol.value,
            base_url=config.base_url,
            model_name=config.model_name,
            api_key_ciphertext=ciphertext,
            embedding_dim=config.embedding_dim,
            enabled=False,
        )
        self._session.add(row)
        self._session.flush()
        return _to_config(row)

    def find_by_id(self, config_id: UUID) -> ModelConfig | None:
        row = self._session.get(ModelConfigRow, config_id)
        return _to_config(row) if row else None

    def list_all(self) -> list[ModelConfig]:
        rows = self._session.scalars(
            select(ModelConfigRow).order_by(
                ModelConfigRow.capability, ModelConfigRow.created_at, ModelConfigRow.id
            )
        ).all()
        return [_to_config(row) for row in rows]

    def find_enabled(self, capability: ModelCapability) -> ModelConfig | None:
        row = self._session.scalars(
            select(ModelConfigRow).where(
                ModelConfigRow.capability == capability.value,
                ModelConfigRow.enabled.is_(True),
            )
        ).one_or_none()
        return _to_config(row) if row else None

    def update(
        self, config_id: UUID, changes: ModelConfigUpdate, *, ciphertext: str | None
    ) -> ModelConfig:
        row = self._session.get(ModelConfigRow, config_id)
        if row is None:
            raise NotFound("模型配置不存在")

        if changes.base_url is not None:
            row.base_url = changes.base_url
        if changes.model_name is not None:
            row.model_name = changes.model_name
        if changes.embedding_dim is not None:
            row.embedding_dim = changes.embedding_dim
        if ciphertext is not None:
            # 换密钥必须递增 version：历史向量与旧凭据的对应关系靠它追溯。
            row.api_key_ciphertext = ciphertext
            row.version += 1
        row.updated_at = utcnow()
        self._session.flush()
        return _to_config(row)

    def enable(self, config_id: UUID) -> ModelConfig:
        row = self._session.get(ModelConfigRow, config_id)
        if row is None:
            raise NotFound("模型配置不存在")

        # 先停用同类能力的其他配置，再启用目标 —— 同一事务内完成，避免触发部分唯一索引冲突。
        self._session.execute(
            update(ModelConfigRow)
            .where(
                ModelConfigRow.capability == row.capability,
                ModelConfigRow.id != row.id,
                ModelConfigRow.enabled.is_(True),
            )
            .values(enabled=False, updated_at=utcnow())
        )
        row.enabled = True
        row.updated_at = utcnow()
        self._session.flush()
        return _to_config(row)

    def ciphertext_of(self, config_id: UUID) -> str | None:
        return self._session.scalar(
            select(ModelConfigRow.api_key_ciphertext).where(ModelConfigRow.id == config_id)
        )
