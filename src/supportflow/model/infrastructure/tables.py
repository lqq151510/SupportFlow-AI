"""model 模块 ORM 表。

两个关键设计：

1. **密钥只存密文**：``api_key_ciphertext`` 是 AES-GCM 输出，明文永不落库，
   也永不进入任何响应或日志（AGENTS.md §4）。
2. **单工作区每类能力只启用一个配置**，由 ``(capability) WHERE enabled`` 的
   部分唯一索引保证 —— 应用层不做「先查后写」判重（同 ``agent_runs`` 的做法）。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from supportflow.model.domain.models import ModelCapability, ModelProtocol
from supportflow.shared.clock import utcnow
from supportflow.shared.db import Base

_CAPABILITY_SQL = ", ".join(f"'{value.value}'" for value in ModelCapability)
_PROTOCOL_SQL = ", ".join(f"'{value.value}'" for value in ModelProtocol)


class ModelConfigRow(Base):
    __tablename__ = "model_configs"
    __table_args__ = (
        CheckConstraint(f"capability IN ({_CAPABILITY_SQL})", name="ck_model_configs_capability"),
        CheckConstraint(f"protocol IN ({_PROTOCOL_SQL})", name="ck_model_configs_protocol"),
        CheckConstraint(
            "embedding_dim IS NULL OR (embedding_dim > 0 AND embedding_dim <= 8192)",
            name="ck_model_configs_embedding_dim",
        ),
        # 每类能力至多一个启用配置。换配置必须先在事务内停用旧的。
        Index(
            "uq_model_configs_enabled_per_capability",
            "capability",
            unique=True,
            postgresql_where=text("enabled"),
        ),
        Index("ix_model_configs_capability_enabled", "capability", "enabled"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    capability: Mapped[str] = mapped_column(String(16))
    protocol: Mapped[str] = mapped_column(String(32))
    base_url: Mapped[str] = mapped_column(String(500))
    model_name: Mapped[str] = mapped_column(String(200))
    api_key_ciphertext: Mapped[str] = mapped_column(Text)
    embedding_dim: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


__all__ = ["ModelConfigRow"]
