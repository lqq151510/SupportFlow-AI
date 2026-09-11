"""agent 模块的领域端口。"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from supportflow.agent.domain.models import (
    AgentRun,
    RunEvent,
    RunEventType,
    RunStatus,
    RunStepRecord,
)


class RunRepositoryPort(Protocol):
    def add(
        self, *, ticket_id: UUID, model_mode: str, retry_of_run_id: UUID | None = None
    ) -> AgentRun: ...

    def find_by_id(self, run_id: UUID) -> AgentRun | None: ...

    def list_for_ticket(self, ticket_id: UUID) -> list[AgentRun]: ...

    def claim(self, run_id: UUID, *, owner: str, lease_seconds: int) -> AgentRun | None:
        """尝试以租约领取该运行；已被他人占住或状态不允许时返回 ``None``。"""
        ...

    def claim_next(self, *, owner: str, lease_seconds: int) -> AgentRun | None:
        """领取最早的一个待执行运行。使用 ``FOR UPDATE SKIP LOCKED``。"""
        ...

    def finish(
        self,
        run_id: UUID,
        *,
        status: RunStatus,
        error_code: str | None = None,
        chat_model_name: str | None = None,
    ) -> None: ...

    def bump_counters(
        self, run_id: UUID, *, steps: int = 0, tool_calls: int = 0
    ) -> None: ...


class RunEventRepositoryPort(Protocol):
    def append(
        self, run_id: UUID, event_type: RunEventType, payload: dict[str, object]
    ) -> int: ...

    def list_since(self, run_id: UUID, *, after_id: int, limit: int) -> list[RunEvent]: ...


class RunStepRepositoryPort(Protocol):
    def add(self, run_id: UUID, step: RunStepRecord) -> None: ...

    def list_steps(self, run_id: UUID) -> list[RunStepRecord]: ...
