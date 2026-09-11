"""Agent 运行的领域模型。

状态机与事件类型是**对外契约**的一部分（SSE 事件名、运行状态），
改动必须同步更新 PLAN.md 与契约文档。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class RunStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    NEEDS_HUMAN = "NEEDS_HUMAN"
    FAILED = "FAILED"

    @property
    def is_terminal(self) -> bool:
        return self in (RunStatus.COMPLETED, RunStatus.NEEDS_HUMAN, RunStatus.FAILED)


#: 占住「同一工单同时只能有一个活动运行」这一约束的状态集合。
#: 与 ``agent_runs`` 上的部分唯一索引条件必须保持一致。
ACTIVE_RUN_STATUSES: tuple[RunStatus, ...] = (
    RunStatus.QUEUED,
    RunStatus.RUNNING,
    RunStatus.WAITING_APPROVAL,
)


class RunEventType(StrEnum):
    RUN_STARTED = "run.started"
    STEP_STARTED = "run.step.started"
    STEP_COMPLETED = "run.step.completed"
    RETRIEVAL_COMPLETED = "retrieval.completed"
    TOOL_REQUESTED = "tool.requested"
    TOOL_COMPLETED = "tool.completed"
    DRAFT_CREATED = "draft.created"
    CITATION_INVALID = "citation.invalid"
    APPROVAL_REQUIRED = "approval.required"
    ACTION_EXECUTED = "action.executed"
    RUN_NEEDS_HUMAN = "run.needs_human"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"


@dataclass(frozen=True, slots=True)
class AgentRun:
    id: UUID
    ticket_id: UUID
    status: RunStatus
    model_mode: str
    chat_model_name: str | None
    error_code: str | None
    step_count: int
    tool_call_count: int
    lease_owner: str | None
    lease_expires_at: datetime | None
    retry_of_run_id: UUID | None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class RunEvent:
    """一次运行事件的只读视图。``id`` 是全局单调序列，用作 SSE 的 ``Last-Event-ID``。"""

    id: int
    run_id: UUID
    event_type: RunEventType
    payload: dict[str, object]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RunStepRecord:
    step_no: int
    node_name: str
    latency_ms: int
    detail: str | None = None
