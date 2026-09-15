"""运行执行器：用 LangGraph 状态图替代阶段 2 的简化管线。

三个不可让步的性质：

1. **每节点一个事务边界。** 节点的步骤账本、事件、业务写入在节点结束时提交，随后
   LangGraph 才写检查点。若进程在节点中途崩溃，该节点的写入整体回滚，重启后重跑该节点
   不会留下半成品；已完成节点由检查点跳过，既不重复调用模型，也不重复写业务结果。
2. **运行终态在图层之外落定。** 图只负责推进状态，``finish`` 与计数器由执行器统一写入，
   因此「图跑完了但进程死了」也能在下次恢复时补齐终态，不会产生第二个业务效果。
3. **网关按运行的模式解析。** 运行可按次指定 ``model_mode``；若沿用装配期的固定网关，
   就会出现「标记 real、实由 Mock 产出」的失真（AGENTS.md §10）。
4. **租约是最后一道闸。** 执行前与 ``persist_result`` 内各校验一次归属，租约被接管即
   放弃写回并保持运行状态不变。

对外契约不变：SSE 事件名沿用阶段 2 的一套名称。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver

from supportflow.agent.application.graph import (
    STATE_COMPLETED,
    STATE_FAILED,
    STATE_LEASE_LOST,
    STATE_NEEDS_HUMAN,
    AgentGraphState,
    GraphDeps,
    build_graph,
)
from supportflow.agent.application.ports import (
    KnowledgeRetrievalPort,
    TicketGatewayPort,
)
from supportflow.agent.domain.models import AgentRun, RunEventType, RunStatus
from supportflow.agent.domain.ports import (
    RunEventRepositoryPort,
    RunRepositoryPort,
    RunStepRepositoryPort,
)
from supportflow.model.domain.gateway import ChatModelGateway
from supportflow.model.infrastructure.factory import GatewayResolver
from supportflow.ticket.application.catalog import label_of, parse_category

logger = logging.getLogger(__name__)

LEASE_LOST = "lease_lost"


@dataclass(frozen=True, slots=True)
class ExecutionOutcome:
    """``status`` 为 ``RUNNING`` 且 ``error_code`` 为 ``lease_lost`` 表示未写回、状态保持原样。"""

    status: RunStatus
    error_code: str | None = None
    category: str | None = None


class RunExecutor:
    def __init__(
        self,
        *,
        gateway_for: GatewayResolver,
        retrieval: KnowledgeRetrievalPort,
        tickets: TicketGatewayPort,
        runs: RunRepositoryPort,
        events: RunEventRepositoryPort,
        steps: RunStepRepositoryPort,
        database_url: str,
        commit: Callable[[], None],
        max_attempts: int,
        checkpointer_factory: Callable[[str], AbstractContextManager[BaseCheckpointSaver]],
        config_for_run: Callable[[UUID], dict[str, Any]],
        base_delay_seconds: float = 0.0,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._gateway_for = gateway_for
        self._retrieval = retrieval
        self._tickets = tickets
        self._runs = runs
        self._events = events
        self._steps = steps
        self._database_url = database_url
        self._commit = commit
        self._max_attempts = max_attempts
        self._base_delay = base_delay_seconds
        self._sleeper = sleeper
        self._checkpointer_factory = checkpointer_factory
        self._config_for_run = config_for_run

    def execute(self, run: AgentRun, *, owner: str) -> ExecutionOutcome:
        if not self._owns(run.id, owner=owner):
            logger.warning("租约已被接管，放弃执行: run_id=%s owner=%s", run.id, owner)
            return ExecutionOutcome(status=RunStatus.RUNNING, error_code=LEASE_LOST)

        # 网关按**本运行**的模式解析：按次指定的 real 必须真的走真实网关。
        gateway = self._gateway_for(run.model_mode)

        deps = GraphDeps(
            gateway=gateway,
            retrieval=self._retrieval,
            tickets=self._tickets,
            runs=self._runs,
            events=self._events,
            steps=self._steps,
            max_attempts=self._max_attempts,
            base_delay_seconds=self._base_delay,
            sleeper=self._sleeper,
            commit=self._commit,
        )
        graph = build_graph(deps)
        config = cast("RunnableConfig", self._config_for_run(run.id))

        with self._checkpointer_factory(self._database_url) as checkpointer:
            compiled = graph.compile(checkpointer=checkpointer)
            resuming = checkpointer.get_tuple(config) is not None
            if resuming:
                # 同一 thread_id 已有检查点：不再重放 run.started，也不重复已完成节点。
                logger.info("从检查点恢复运行: run_id=%s", run.id)
                state = compiled.invoke(None, config)
            else:
                self._emit_started(run, owner=owner, gateway=gateway)
                state = compiled.invoke(self._initial_state(run, owner), config)

        return self._finalize(run, state, gateway=gateway)

    # --- 内部 ---------------------------------------------------------------

    def _initial_state(self, run: AgentRun, owner: str) -> AgentGraphState:
        return {
            "run_id": str(run.id),
            "ticket_id": str(run.ticket_id),
            "owner": owner,
            "model_mode": run.model_mode,
            "evidence": [],
            "tool_calls": 0,
            "tool_trace": [],
            "next_step_no": 1,
        }

    def _emit_started(
        self, run: AgentRun, *, owner: str, gateway: ChatModelGateway
    ) -> None:
        self._events.append(
            run.id,
            RunEventType.RUN_STARTED,
            {"model_mode": run.model_mode, "model": gateway.model_name, "owner": owner},
        )
        self._commit()

    def _owns(self, run_id: UUID, *, owner: str) -> bool:
        current = self._runs.find_by_id(run_id)
        return (
            current is not None
            and current.status is RunStatus.RUNNING
            and current.lease_owner == owner
        )

    def _finalize(
        self, run: AgentRun, state: dict[str, object], *, gateway: ChatModelGateway
    ) -> ExecutionOutcome:
        status = str(state.get("status") or STATE_FAILED)
        steps = max(_as_int(state.get("next_step_no"), 1) - 1, 0)
        tool_calls = _as_int(state.get("tool_calls"))

        if status == STATE_LEASE_LOST:
            logger.warning("租约已被接管，放弃写回: run_id=%s", run.id)
            return ExecutionOutcome(status=RunStatus.RUNNING, error_code=LEASE_LOST)

        # 计数器写绝对值而不是累加：恢复重放时不会把同一步骤数两次。
        self._runs.set_counters(run.id, steps=steps, tool_calls=tool_calls)

        if status == STATE_COMPLETED:
            self._runs.finish(
                run.id,
                status=RunStatus.COMPLETED,
                chat_model_name=str(state.get("model_name") or gateway.model_name),
            )
            category = str(state.get("category") or "")
            parsed = parse_category(category)
            self._events.append(
                run.id,
                RunEventType.RUN_COMPLETED,
                {
                    "category": category,
                    "category_label": label_of(parsed) if parsed else "",
                    "confidence": _as_float(state.get("category_confidence")),
                    "rationale": str(state.get("category_rationale") or ""),
                    "model": str(state.get("model_name") or gateway.model_name),
                    "model_mode": run.model_mode,
                    "citation_count": len(_as_list(state.get("citations"))),
                    "tool_calls": tool_calls,
                },
            )
            self._commit()
            return ExecutionOutcome(
                status=RunStatus.COMPLETED, category=category or None
            )

        if status == STATE_NEEDS_HUMAN:
            reason = str(state.get("handoff_reason") or "unknown")
            self._runs.finish(run.id, status=RunStatus.NEEDS_HUMAN, error_code=reason)
            self._events.append(
                run.id,
                RunEventType.RUN_NEEDS_HUMAN,
                {"reason": reason, "detail": str(state.get("detail") or "")[:400]},
            )
            self._commit()
            logger.info("运行转人工: run_id=%s reason=%s", run.id, reason)
            return ExecutionOutcome(status=RunStatus.NEEDS_HUMAN, error_code=reason)

        code = str(state.get("error_code") or "execution_failed")
        self._runs.finish(run.id, status=RunStatus.FAILED, error_code=code)
        self._events.append(
            run.id,
            RunEventType.RUN_FAILED,
            {"error_code": code, "detail": str(state.get("detail") or "")[:400]},
        )
        self._commit()
        logger.warning("运行失败: run_id=%s code=%s", run.id, code)
        return ExecutionOutcome(status=RunStatus.FAILED, error_code=code)


def _as_int(value: object, default: int = 0) -> int:
    return value if isinstance(value, int) else default


def _as_float(value: object) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []
