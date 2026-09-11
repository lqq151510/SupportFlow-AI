"""运行的应用服务（查询与人工重试）。

首次运行的创建在 ``agent.application.scheduler.FirstRunScheduler`` —— 它只依赖运行
仓储，避免与 ``TicketService`` 形成装配环。

人工重试同样要求 ``Idempotency-Key``：客户端在超时后重发必须拿到**同一个**
``run_id``，而不是撞上 ``run_already_active``。
"""

from __future__ import annotations

from uuid import UUID

from supportflow.agent.application.ports import TicketLookupPort
from supportflow.agent.domain.models import AgentRun, RunEvent
from supportflow.agent.domain.ports import (
    RunEventRepositoryPort,
    RunRepositoryPort,
    RunStepRepositoryPort,
)
from supportflow.identity.domain.models import Principal
from supportflow.shared.errors import Forbidden, ModelModeUnavailable, NotFound
from supportflow.shared.idempotency import IdempotencyPort, fingerprint

DEFAULT_EVENT_PAGE_SIZE = 200
START_RUN_SCOPE = "POST /api/v1/tickets/{ticket_id}/runs"


class RunService:
    def __init__(
        self,
        runs: RunRepositoryPort,
        events: RunEventRepositoryPort,
        steps: RunStepRepositoryPort,
        tickets: TicketLookupPort,
        idempotency: IdempotencyPort,
        *,
        default_model_mode: str,
        available_model_modes: frozenset[str],
    ) -> None:
        self._runs = runs
        self._events = events
        self._steps = steps
        self._tickets = tickets
        self._idempotency = idempotency
        self._default_model_mode = default_model_mode
        self._available_model_modes = available_model_modes

    # --- 查询 ---------------------------------------------------------------
    def get_run(self, principal: Principal, run_id: UUID) -> AgentRun:
        run = self._runs.find_by_id(run_id)
        if run is None:
            raise NotFound("运行不存在")
        # 复用 ticket 模块的可见性判定：可见工单的运行才可见。
        self._tickets.get_ticket(principal, run.ticket_id)
        return run

    def list_runs(self, principal: Principal, ticket_id: UUID) -> list[AgentRun]:
        self._tickets.get_ticket(principal, ticket_id)
        return self._runs.list_for_ticket(ticket_id)

    def list_events(
        self,
        principal: Principal,
        run_id: UUID,
        *,
        after_id: int = 0,
        limit: int = DEFAULT_EVENT_PAGE_SIZE,
    ) -> list[RunEvent]:
        self.get_run(principal, run_id)
        return self._events.list_since(run_id, after_id=after_id, limit=limit)

    # --- 人工重试 -----------------------------------------------------------
    def start_new_run(
        self,
        principal: Principal,
        ticket_id: UUID,
        *,
        idempotency_key: str,
        model_mode: str | None = None,
    ) -> AgentRun:
        """创建关联原记录的新运行；不原地复活旧运行。

        顺序很重要：先做可见性与角色校验，再占用幂等键 —— 被拒绝的请求不应
        消耗客户端后续要用的幂等键。
        """
        ticket = self._tickets.get_ticket(principal, ticket_id)
        if not principal.is_staff:
            raise Forbidden("仅坐席与管理员可以手动发起运行")
        mode = model_mode or self._default_model_mode
        if mode not in self._available_model_modes:
            raise ModelModeUnavailable(
                f"当前构建只提供 {'、'.join(sorted(self._available_model_modes))} 模式"
            )

        request_hash = fingerprint({"ticket_id": str(ticket.id), "model_mode": mode})
        replayed = self._idempotency.reserve(START_RUN_SCOPE, idempotency_key, request_hash)
        if replayed is not None:
            run = self._runs.find_by_id(UUID(str(replayed.body["run_id"])))
            if run is None:  # pragma: no cover - 运行随工单级联删除后才会出现
                raise NotFound("运行不存在")
            return run

        # 该工单已有活动运行时，部分唯一索引会触发 RunAlreadyActive(409)，
        # 事务回滚会连带撤销上面的幂等键占位。
        previous = self._runs.list_for_ticket(ticket.id)
        run = self._runs.add(
            ticket_id=ticket.id,
            model_mode=mode,
            # 关联上一次运行，便于「同一工单不同运行的对比」；不原地复活旧记录。
            retry_of_run_id=previous[-1].id if previous else None,
        )
        self._idempotency.complete(
            START_RUN_SCOPE,
            idempotency_key,
            status_code=202,
            body={
                "run_id": str(run.id),
                "ticket_id": str(run.ticket_id),
                "status": run.status.value,
                "model_mode": run.model_mode,
            },
        )
        return run
