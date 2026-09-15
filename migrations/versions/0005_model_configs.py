"""模型配置（聊天与 Embedding 分别配置，API Key 只存密文）。

设计说明：

- ``api_key_ciphertext`` 存 AES-GCM 密文（``v1.<nonce>.<ct>``）。明文 Key 永不落库；
  主密钥只来自 ``MODEL_SECRET_MASTER_KEY`` 环境变量。
- ``(capability) WHERE enabled`` 为**部分唯一索引**：单工作区每类能力至多一个启用配置。
  换配置必须在一个事务里先停用旧的，而不是依赖应用层「先查后写」。
- 访问路径：按 ``capability`` 判定「该能力是否已启用」（运行期装配真实网关）、
  按 ``(capability, enabled)`` 列配置列表。

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-15
"""
# ruff: noqa: E501

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("capability", sa.String(16), nullable=False),
        sa.Column("protocol", sa.String(32), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("api_key_ciphertext", sa.Text(), nullable=False),
        sa.Column("embedding_dim", sa.Integer(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_model_configs"),
        sa.CheckConstraint(
            "capability IN ('CHAT', 'EMBEDDING')", name="ck_model_configs_capability"
        ),
        sa.CheckConstraint(
            "protocol IN ('OPENAI_COMPATIBLE')", name="ck_model_configs_protocol"
        ),
        sa.CheckConstraint(
            "embedding_dim IS NULL OR (embedding_dim > 0 AND embedding_dim <= 8192)",
            name="ck_model_configs_embedding_dim",
        ),
    )
    op.create_index(
        "uq_model_configs_enabled_per_capability",
        "model_configs",
        ["capability"],
        unique=True,
        postgresql_where=sa.text("enabled"),
    )
    op.create_index(
        "ix_model_configs_capability_enabled", "model_configs", ["capability", "enabled"]
    )


def downgrade() -> None:
    op.drop_table("model_configs")
