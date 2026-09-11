"""依赖装配（composition root）。

这是**唯一**允许同时导入各业务模块 ``infrastructure`` 的地方。``api`` 层从这里取得
装配好的应用服务 —— 这是「api -> application」规则的一处受控例外：api 依赖的是组合根
本身，而不是任何业务模块的内部实现。

装配顺序刻意避免环：``FirstRunScheduler``（只依赖运行仓储）→ ``TicketService`` →
``RunService``（引用 ``TicketService`` 做可见性判定）。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from supportflow.agent.application.executor import RunExecutor
from supportflow.agent.application.scheduler import FirstRunScheduler
from supportflow.agent.application.service import RunService
from supportflow.agent.application.worker import RunExecutionUnit
from supportflow.agent.domain.models import RunEvent, RunStatus
from supportflow.agent.infrastructure.partitions import ensure_run_event_partitions
from supportflow.agent.infrastructure.repository import (
    SqlAlchemyRunEventRepository,
    SqlAlchemyRunRepository,
    SqlAlchemyRunStepRepository,
)
from supportflow.identity.application.service import AuthService
from supportflow.identity.infrastructure.repository import (
    SqlAlchemySessionRepository,
    SqlAlchemyUserRepository,
)
from supportflow.identity.infrastructure.security import (
    Argon2PasswordHasher,
    SecureTokenSource,
)
from supportflow.model.domain.gateway import ChatModelGateway
from supportflow.model.infrastructure.factory import available_model_modes, build_chat_gateway
from supportflow.shared.audit import AuditRecorder
from supportflow.shared.config import Settings, get_settings
from supportflow.shared.db import session_scope
from supportflow.shared.idempotency import IdempotencyStore
from supportflow.ticket.application.service import TicketService
from supportflow.ticket.infrastructure.repository import SqlAlchemyTicketRepository


@dataclass(frozen=True, slots=True)
class Services:
    settings: Settings
    session: Session
    auth: AuthService
    tickets: TicketService
    runs: RunService
    audit: AuditRecorder
    gateway: ChatModelGateway


def build_services(session: Session, settings: Settings | None = None) -> Services:
    cfg = settings or get_settings()
    token_source = SecureTokenSource()

    users = SqlAlchemyUserRepository(session)
    user_sessions = SqlAlchemySessionRepository(session)
    tickets_repo = SqlAlchemyTicketRepository(session)
    runs_repo = SqlAlchemyRunRepository(session)
    events_repo = SqlAlchemyRunEventRepository(session)
    steps_repo = SqlAlchemyRunStepRepository(session)

    auth = AuthService(
        users,
        user_sessions,
        Argon2PasswordHasher(),
        token_source,
        session_ttl_seconds=cfg.session_ttl_seconds,
    )
    available_modes = available_model_modes()
    tickets = TicketService(
        tickets_repo,
        IdempotencyStore(session),
        FirstRunScheduler(runs_repo),
        default_model_mode=cfg.model_mode,
        available_model_modes=available_modes,
    )
    runs = RunService(
        runs_repo,
        events_repo,
        steps_repo,
        tickets,
        IdempotencyStore(session),
        default_model_mode=cfg.model_mode,
        available_model_modes=available_modes,
    )
    return Services(
        settings=cfg,
        session=session,
        auth=auth,
        tickets=tickets,
        runs=runs,
        audit=AuditRecorder(session),
        gateway=build_chat_gateway(cfg),
    )


@contextmanager
def services_scope(settings: Settings | None = None) -> Iterator[Services]:
    """请求级依赖：一个 Session 对应一个 HTTP 请求的完整事务。"""
    with session_scope() as session:
        yield build_services(session, settings)


# --- Worker 用 -----------------------------------------------------------------


@contextmanager
def execution_unit_scope(settings: Settings | None = None) -> Iterator[RunExecutionUnit]:
    """为 Worker 组装一次执行所需的协作者（独立事务）。"""
    cfg = settings or get_settings()
    with session_scope() as session:
        runs_repo = SqlAlchemyRunRepository(session)
        executor = RunExecutor(
            gateway=build_chat_gateway(cfg),
            runs=runs_repo,
            events=SqlAlchemyRunEventRepository(session),
            steps=SqlAlchemyRunStepRepository(session),
            tickets=SqlAlchemyTicketRepository(session),
            max_attempts=cfg.model_max_attempts,
            base_delay_seconds=0.5,
        )
        yield RunExecutionUnit(runs=runs_repo, executor=executor)


# --- 启动期准备 ----------------------------------------------------------------


def prepare_database() -> list[str]:
    """预建运行事件分区。API 与 Worker 启动时都应调用。"""
    with session_scope() as session:
        return ensure_run_event_partitions(session)


# --- SSE 专用读取路径 -----------------------------------------------------------


def authorize_run_access(session_token: str | None, run_id: UUID) -> None:
    """在**独立的短事务**里完成鉴权。

    流式响应期间请求级 Session 会一直被持有（可能长达数十秒），会挤占连接池。
    因此 SSE 路由不使用共享依赖，而是先在这个短事务里鉴权，再开始推送。
    """
    with services_scope() as services:
        principal = services.auth.resolve_principal(session_token)
        services.runs.get_run(principal, run_id)


def poll_run_events(run_id: UUID, *, after_id: int, limit: int = 200) -> list[RunEvent]:
    with session_scope() as session:
        return SqlAlchemyRunEventRepository(session).list_since(
            run_id, after_id=after_id, limit=limit
        )


def current_run_status(run_id: UUID) -> RunStatus | None:
    with session_scope() as session:
        run = SqlAlchemyRunRepository(session).find_by_id(run_id)
        return run.status if run else None
