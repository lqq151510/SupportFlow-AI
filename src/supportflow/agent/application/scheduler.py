"""首次运行调度器。

``FirstRunSchedulerPort`` 的实现刻意**只依赖运行仓储**，不复用 ``RunService``：
``RunService`` 需要 ``TicketService`` 做可见性判定，而 ``TicketService`` 又需要
调度器来创建首次运行 —— 若让两者互相引用就会形成装配环。

容器用同一个请求级 Session 构造调度器与 ``TicketService``，因此
「创建工单」与「创建首次运行」仍在同一事务内提交。
"""

from __future__ import annotations

from uuid import UUID

from supportflow.agent.domain.ports import RunRepositoryPort


class FirstRunScheduler:
    def __init__(self, runs: RunRepositoryPort) -> None:
        self._runs = runs

    def schedule_first_run(self, *, ticket_id: UUID, model_mode: str) -> UUID:
        run = self._runs.add(ticket_id=ticket_id, model_mode=model_mode)
        return run.id
