"""评测集、评测运行与结果（PLAN 表 #19 / #20 / #21）。

「冻结」的设计：用例与知识语料一起版本化在 ``evaluation/frozen/cases.json``，
``expected_source_ids`` 引用冻结语料的**文档标题**，因此 Recall@5 可跨环境复现。

回滚：三张表整体删除。评测数据是派生数据，回滚不损失业务事实。

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-16
"""
# ruff: noqa: E501

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evaluation_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_key", sa.String(64), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("expected_ticket_category", sa.String(32), nullable=True),
        sa.Column("expected_source_ids", JSONB(), nullable=False),
        sa.Column("expected_tools", JSONB(), nullable=False),
        sa.Column("expect_handoff", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_evaluation_cases"),
        sa.UniqueConstraint("case_key", name="uq_evaluation_cases_case_key"),
        sa.CheckConstraint(
            "expect_handoff IN (true, false)", name="ck_evaluation_cases_expect_handoff"
        ),
    )
    op.create_index(
        "ix_evaluation_cases_category_enabled", "evaluation_cases", ["category", "enabled"]
    )

    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("model_config_id", sa.Uuid(), nullable=True),
        sa.Column("index_version", sa.String(64), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("metrics_json", JSONB(), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_evaluation_runs"),
        sa.ForeignKeyConstraint(
            ["model_config_id"],
            ["model_configs.id"],
            name="fk_evaluation_runs_model_config_id",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')",
            name="ck_evaluation_runs_status",
        ),
    )
    op.create_index("ix_evaluation_runs_created", "evaluation_runs", ["created_at"])

    op.create_table(
        "evaluation_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("draft_content", sa.Text(), nullable=True),
        sa.Column("citations", JSONB(), nullable=True),
        sa.Column("category_correct", sa.Boolean(), nullable=True),
        sa.Column("recall_at_5", sa.Boolean(), nullable=True),
        sa.Column("citation_valid", sa.Boolean(), nullable=True),
        sa.Column("tool_correct", sa.Boolean(), nullable=True),
        sa.Column("handoff_correct", sa.Boolean(), nullable=True),
        sa.Column("detail_json", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_evaluation_results"),
        sa.ForeignKeyConstraint(
            ["run_id"], ["evaluation_runs.id"], name="fk_evaluation_results_run_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["evaluation_cases.id"],
            name="fk_evaluation_results_case_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("run_id", "case_id", name="uq_evaluation_results_run_case"),
    )
    op.create_index(
        "ix_evaluation_results_run_correct", "evaluation_results", ["run_id", "category_correct"]
    )


def downgrade() -> None:
    op.drop_table("evaluation_results")
    op.drop_table("evaluation_runs")
    op.drop_table("evaluation_cases")
