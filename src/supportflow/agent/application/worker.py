"""Agent Worker。

与 API 进程分离，独立轮询领取待执行运行。

**两段式事务**是这里的关键：领取（``claim``）与执行必须分成两个事务提交。
若放在同一事务里，``FOR UPDATE SKIP LOCKED`` 的锁会一直持有到执行结束，
``RUNNING`` 状态对其他 Worker 不可见，租约机制形同虚设。

租约回收：状态为 ``RUNNING`` 且 ``lease_expires_at`` 已过期的运行会被重新领取，
因此 Worker 崩溃后未完成的任务不会被永久卡住 —— 见 PLAN.md「Worker 重启后可以
重新领取未完成任务」。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass

from supportflow.agent.application.executor import RunExecutor
from supportflow.agent.domain.ports import RunRepositoryPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RunExecutionUnit:
    """一次执行所需的协作者集合，由 ``bootstrap`` 组装。"""

    runs: RunRepositoryPort
    executor: RunExecutor


class AgentWorker:
    def __init__(
        self,
        *,
        open_unit: Callable[[], AbstractContextManager[RunExecutionUnit]],
        owner: str,
        lease_seconds: int,
        poll_interval_seconds: float,
        max_iterations: int | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._open_unit = open_unit
        self._owner = owner
        self._lease_seconds = lease_seconds
        self._poll_interval = poll_interval_seconds
        self._max_iterations = max_iterations
        self._sleep = sleeper

    def run_forever(self) -> None:
        iterations = 0
        while self._max_iterations is None or iterations < self._max_iterations:
            iterations += 1
            if not self.run_once():
                self._sleep(self._poll_interval)

    def run_once(self) -> bool:
        """领取并执行一个运行。返回 ``True`` 表示本次确实处理了任务。"""
        # 事务 1：领取并立即提交租约。
        with self._open_unit() as unit:
            run = unit.runs.claim_next(
                owner=self._owner, lease_seconds=self._lease_seconds
            )
        if run is None:
            return False

        # 事务 2：执行并提交结果。
        with self._open_unit() as execution_unit:
            outcome = execution_unit.executor.execute(run, owner=self._owner)
        logger.info(
            "运行处理完成: run_id=%s status=%s error=%s",
            run.id,
            outcome.status.value,
            outcome.error_code,
        )
        return True
