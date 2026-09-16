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

    def park_waiting_approval(self, run_id: UUID) -> None:
        """把运行停在 ``WAITING_APPROVAL`` 并释放租约。

        **不是终态**：不写 ``finished_at``。审批决定后由审批模块推进终态。
        """
        ...

    def finish(
        self,
        run_id: UUID,
        *,
        status: RunStatus,
        error_code: str | None = None,
        chat_model_name: str | None = None,
    ) -> None: ...

    def set_counters(self, run_id: UUID, *, steps: int, tool_calls: int) -> None:
        """按绝对值写入计数器。

        检查点重放会重复调用本方法，累加语义会把同一步骤数两次，因此这里以状态的
        实际步数为准做覆盖写 —— 幂等边界在「状态」而不是「调用次数」。
        """
        ...


class RunEventRepositoryPort(Protocol):
    def append(
        self, run_id: UUID, event_type: RunEventType, payload: dict[str, object]
    ) -> int: ...

    def list_since(self, run_id: UUID, *, after_id: int, limit: int) -> list[RunEvent]: ...


class RunStepRepositoryPort(Protocol):
    def upsert(self, run_id: UUID, step: RunStepRecord) -> None:
        """按 ``(run_id, step_no)`` 主键写入或覆盖。

        使用 upsert 而不是 insert：崩溃恢复重跑同一个节点时步骤号不变，
        覆盖写保证账本不出现重复行，``step_count`` 也保持稳定。
        """
        ...

    def list_steps(self, run_id: UUID) -> list[RunStepRecord]: ...
