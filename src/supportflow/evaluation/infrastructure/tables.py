"""评测集、评测运行与结果（PLAN 表 #19 / #20 / #21）。

「冻结」的含义：用例与知识语料一起版本化（``frozen/cases.json``），
`expected_source_ids` 引用冻结语料的**文档标题**（种子后即稳定 ID），
因此 Recall@5 在任何环境都可复现，不依赖运行期生成的随机 ID。

``evaluation_results`` 每个用例一行，逐项记录是否命中；
``evaluation_runs.metrics_json`` 存聚合指标。两者都只追加。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from supportflow.shared.clock import utcnow
from supportflow.shared.db import Base

_EVAL_STATUS_SQL = "('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')"


class EvaluationCaseRow(Base):
    __tablename__ = "evaluation_cases"
    __table_args__ = (
        CheckConstraint(
            "expect_handoff IN (true, false)", name="ck_evaluation_cases_expect_handoff"
        ),
        # PLAN 表 #19 指定的访问路径：按分组与启用状态取用例。
        Index("ix_evaluation_cases_category_enabled", "category", "enabled"),
        UniqueConstraint("case_key", name="uq_evaluation_cases_case_key"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    #: 冻结集里的稳定标识（如 "retrieval-delivery-01"），导入的幂等键。
    case_key: Mapped[str] = mapped_column(String(64))
    #: 分组：retrieval / safety / failure 等，对应 PLAN 的 40 检索 + 10 安全。
    category: Mapped[str] = mapped_column(String(32))
    subject: Mapped[str] = mapped_column(String(200))
    question: Mapped[str] = mapped_column(Text)
    expected_ticket_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    #: 期望命中的冻结语料文档标题列表（JSON 数组）。
    expected_source_ids: Mapped[list[object]] = mapped_column(JSONB)
    expected_tools: Mapped[list[object]] = mapped_column(JSONB)
    expect_handoff: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EvaluationRunRow(Base):
    __tablename__ = "evaluation_runs"
    __table_args__ = (
        CheckConstraint(f"status IN {_EVAL_STATUS_SQL}", name="ck_evaluation_runs_status"),
        Index("ix_evaluation_runs_created", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    #: 评测时启用的聊天配置；Mock 模式为空。
    model_config_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("model_configs.id", ondelete="SET NULL"), nullable=True
    )
    #: 评测时生效的索引版本 —— 换索引版本后必须重新评测。
    index_version: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    metrics_json: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EvaluationResultRow(Base):
    __tablename__ = "evaluation_results"
    __table_args__ = (
        UniqueConstraint("run_id", "case_id", name="uq_evaluation_results_run_case"),
        Index("ix_evaluation_results_run_correct", "run_id", "category_correct"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE")
    )
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("evaluation_cases.id", ondelete="RESTRICT")
    )
    draft_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations: Mapped[list[object] | None] = mapped_column(JSONB, nullable=True)
    category_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    recall_at_5: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    citation_valid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    tool_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    handoff_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    detail_json: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
