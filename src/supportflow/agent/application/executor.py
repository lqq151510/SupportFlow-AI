"""运行执行器（阶段 2 版本）。

管线：``run.started → load_ticket → classify_clean → persist_result → run.completed``。

阶段 3 会用完整的 LangGraph 状态图替换本执行器（检索、工具调用、引用校验、审批），
但**节点命名与事件契约保持不变**，因此替换不会影响已发布的 SSE 契约与前端。

租约保护：写回结果之前重新确认自己仍持有该运行的租约。若租约已被回收（例如上一次
执行超时、被其他 Worker 接管），则放弃写回并保持运行状态不变 —— 避免重复的
「至多一次业务效果」被破坏。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from supportflow.agent.application.classification import (
    build_request,
    parse_classification,
)
from supportflow.agent.application.retry import with_retries
from supportflow.agent.domain.models import (
    AgentRun,
    RunEventType,
    RunStatus,
    RunStepRecord,
)
from supportflow.agent.domain.ports import (
    RunEventRepositoryPort,
    RunRepositoryPort,
    RunStepRepositoryPort,
)
from supportflow.model.domain.gateway import ChatModelGateway
from supportflow.shared.errors import ModelResponseInvalid, ModelUnavailable
from supportflow.ticket.application.catalog import label_of
from supportflow.ticket.domain.ports import TicketRepositoryPort

logger = logging.getLogger(__name__)

NODE_LOAD = "load_ticket"
NODE_CLASSIFY = "classify_clean"
NODE_PERSIST = "persist_result"

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
        gateway: ChatModelGateway,
        runs: RunRepositoryPort,
        events: RunEventRepositoryPort,
        steps: RunStepRepositoryPort,
        tickets: TicketRepositoryPort,
        max_attempts: int,
        base_delay_seconds: float = 0.0,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._gateway = gateway
        self._runs = runs
        self._events = events
        self._steps = steps
        self._tickets = tickets
        self._max_attempts = max_attempts
        self._base_delay = base_delay_seconds
        self._sleeper = sleeper

    def execute(self, run: AgentRun, *, owner: str) -> ExecutionOutcome:
        self._events.append(
            run.id,
            RunEventType.RUN_STARTED,
            {"model_mode": run.model_mode, "model": self._gateway.model_name, "owner": owner},
        )

        # --- 1. 载入工单 ---------------------------------------------------
        self._events.append(
            run.id, RunEventType.STEP_STARTED, {"step_no": 1, "node": NODE_LOAD}
        )
        load_started = time.perf_counter()
        ticket = self._tickets.find_by_id(run.ticket_id)
        if ticket is None:
            return self._mark_failed(run, "ticket_missing", "工单不存在")
        self._record_step(
            run,
            step_no=1,
            node=NODE_LOAD,
            started=load_started,
            detail=f"ticket_no={ticket.ticket_no} clean_version={ticket.clean_version}",
        )

        # --- 2. 分类（瞬时错误退避重试） ------------------------------------
        self._events.append(
            run.id, RunEventType.STEP_STARTED, {"step_no": 2, "node": NODE_CLASSIFY}
        )
        classify_started = time.perf_counter()
        try:
            completion = with_retries(
                lambda: self._gateway.complete(
                    build_request(subject=ticket.subject, body_cleaned=ticket.body_cleaned)
                ),
                attempts=self._max_attempts,
                base_delay_seconds=self._base_delay,
                retry_on=(ModelUnavailable,),
                sleeper=self._sleeper,
                label="classify",
            )
            outcome = parse_classification(completion.text)
        except ModelResponseInvalid as exc:
            return self._mark_failed(run, "model_response_invalid", str(exc))
        except ModelUnavailable as exc:
            return self._mark_failed(run, "model_unavailable", str(exc))

        self._record_step(
            run,
            step_no=2,
            node=NODE_CLASSIFY,
            started=classify_started,
            detail=(
                f"{outcome.category.value} confidence={outcome.confidence} "
                f"usage={completion.usage.prompt_tokens}/{completion.usage.completion_tokens}"
            ),
        )

        # --- 3. 写回结果（先确认仍持有租约） --------------------------------
        if not self._still_owns(run, owner=owner):
            logger.warning("租约已被接管，放弃写回: run_id=%s", run.id)
            return ExecutionOutcome(status=RunStatus.RUNNING, error_code=LEASE_LOST)

        self._events.append(
            run.id, RunEventType.STEP_STARTED, {"step_no": 3, "node": NODE_PERSIST}
        )
        persist_started = time.perf_counter()
        self._tickets.assign_category(run.ticket_id, outcome.category)
        self._record_step(
            run,
            step_no=3,
            node=NODE_PERSIST,
            started=persist_started,
            detail=f"category={outcome.category.value}",
        )

        self._runs.bump_counters(run.id, steps=3)
        self._runs.finish(
            run.id, status=RunStatus.COMPLETED, chat_model_name=self._gateway.model_name
        )
        self._events.append(
            run.id,
            RunEventType.RUN_COMPLETED,
            {
                "category": outcome.category.value,
                "category_label": label_of(outcome.category),
                "confidence": outcome.confidence,
                "rationale": outcome.rationale,
                "model": completion.model_name,
                "model_mode": completion.mode.value,
            },
        )
        return ExecutionOutcome(status=RunStatus.COMPLETED, category=outcome.category.value)

    # --- 内部 ---------------------------------------------------------------
    def _still_owns(self, run: AgentRun, *, owner: str) -> bool:
        current = self._runs.find_by_id(run.id)
        return (
            current is not None
            and current.status is RunStatus.RUNNING
            and current.lease_owner == owner
        )

    def _record_step(
        self, run: AgentRun, *, step_no: int, node: str, started: float, detail: str
    ) -> None:
        latency_ms = int((time.perf_counter() - started) * 1000)
        self._steps.add(
            run.id,
            RunStepRecord(
                step_no=step_no, node_name=node, latency_ms=latency_ms, detail=detail
            ),
        )
        self._events.append(
            run.id,
            RunEventType.STEP_COMPLETED,
            {"step_no": step_no, "node": node, "latency_ms": latency_ms},
        )

    def _mark_failed(self, run: AgentRun, code: str, detail: str) -> ExecutionOutcome:
        self._runs.finish(run.id, status=RunStatus.FAILED, error_code=code)
        self._events.append(
            run.id,
            RunEventType.RUN_FAILED,
            {"error_code": code, "detail": detail[:400]},
        )
        logger.warning("运行失败: run_id=%s code=%s", run.id, code)
        return ExecutionOutcome(status=RunStatus.FAILED, error_code=code)
