"""agent 接口契约。

事件类型名（``run.started`` 等）是**对外契约**：前端按 ``event:`` 字段分发，
改动必须同步 PLAN.md 与契约文档。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from supportflow.agent.domain.models import AgentRun, RunEvent


class RunOut(BaseModel):
    id: str
    ticket_id: str
    status: str
    model_mode: str
    chat_model_name: str | None
    error_code: str | None
    step_count: int
    tool_call_count: int
    retry_of_run_id: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def of(cls, run: AgentRun) -> RunOut:
        return cls(
            id=str(run.id),
            ticket_id=str(run.ticket_id),
            status=run.status.value,
            model_mode=run.model_mode,
            chat_model_name=run.chat_model_name,
            error_code=run.error_code,
            step_count=run.step_count,
            tool_call_count=run.tool_call_count,
            retry_of_run_id=str(run.retry_of_run_id) if run.retry_of_run_id else None,
            created_at=run.created_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
        )


class RunListOut(BaseModel):
    items: list[RunOut]


class RunEventOut(BaseModel):
    id: int
    run_id: str
    event_type: str
    payload: dict[str, object]
    created_at: datetime

    @classmethod
    def of(cls, event: RunEvent) -> RunEventOut:
        return cls(
            id=event.id,
            run_id=str(event.run_id),
            event_type=event.event_type.value,
            payload=event.payload,
            created_at=event.created_at,
        )


class StartRunRequest(BaseModel):
    #: 仅坐席与管理员可用；普通用户调用该接口本身就会 403。
    model_mode: str | None = Field(default=None, pattern="^(mock|real)$")
