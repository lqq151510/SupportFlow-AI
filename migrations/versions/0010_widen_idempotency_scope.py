"""放宽幂等键 scope 列宽度（64 → 255）。

阶段 4 起，包含 UUID 路径的接口（如 ``PATCH /api/v1/tickets/{id}/drafts/{id}``）
也接入了幂等键，其 scope 字符串超过 64 字符会触发 ``value too long``。放宽到 255
足以容纳「方法 + 路径 + 两个 UUID」的最长形态。

这是纯加宽（varchar 长度），属于 expand 操作：不丢数据、不阻塞读写，无需回滚数据。
旧数据的 scope 均短于 64，迁移后原样保留。

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-16
"""
# ruff: noqa: E501

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "idempotency_records",
        "scope",
        type_=sa.String(255),
        existing_type=sa.String(64),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "idempotency_records",
        "scope",
        type_=sa.String(64),
        existing_type=sa.String(255),
        existing_nullable=False,
    )
