"""Agent Worker 进程入口。

与 API 进程**分开部署**：Worker 负责执行运行，API 只负责接单与推送事件。
两者共享数据库，通过 ``agent_runs`` 的租约与 ``FOR UPDATE SKIP LOCKED`` 协作，
因此可以水平扩展多个 Worker 而不会重复执行。

用法::

    python -m supportflow.bootstrap.worker
"""

from __future__ import annotations

import logging

from supportflow.agent.application.worker import AgentWorker
from supportflow.bootstrap.container import build_services, execution_unit_scope, prepare_database
from supportflow.shared.config import get_settings
from supportflow.shared.db import session_scope
from supportflow.shared.logging import configure_logging

logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    prepare_database()

    def sweep_expired_approvals() -> None:
        """轮询前清扫到期申请（EXPIRED 由这里独占写入）。"""
        with session_scope() as session:
            build_services(session).approvals.expire_due()

    worker = AgentWorker(
        open_unit=execution_unit_scope,
        owner=settings.worker_lease_owner,
        lease_seconds=settings.run_lease_seconds,
        poll_interval_seconds=settings.worker_poll_interval_seconds,
        pre_poll=sweep_expired_approvals,
    )
    logger.info(
        "Worker 启动：owner=%s lease=%ss model_mode=%s",
        settings.worker_lease_owner,
        settings.run_lease_seconds,
        settings.model_mode,
    )
    try:
        worker.run_forever()
    except KeyboardInterrupt:  # pragma: no cover - 交互式中断
        logger.info("Worker 收到中断信号，正在退出")


if __name__ == "__main__":  # pragma: no cover
    main()
