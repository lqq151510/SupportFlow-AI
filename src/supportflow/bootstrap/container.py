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
from supportflow.agent.application.ports import (
    ActionProposalOutcome,
    Evidence,
    KnowledgeRetrievalPort,
    TicketFacts,
)
from supportflow.agent.application.scheduler import FirstRunScheduler
from supportflow.agent.application.service import RunService
from supportflow.agent.application.worker import RunExecutionUnit
from supportflow.agent.domain.models import RunEvent, RunEventType, RunStatus
from supportflow.agent.domain.models import RunStatus as RunStatusEnum
from supportflow.agent.infrastructure.checkpoints import (
    checkpoint_config,
    postgres_checkpointer,
)
from supportflow.agent.infrastructure.partitions import ensure_run_event_partitions
from supportflow.agent.infrastructure.repository import (
    SqlAlchemyRunEventRepository,
    SqlAlchemyRunRepository,
    SqlAlchemyRunStepRepository,
)
from supportflow.approval.application.service import ActionApprovalService
from supportflow.approval.infrastructure.repository import (
    SqlAlchemyActionLedgerRepository,
    SqlAlchemyActionRequestRepository,
)
from supportflow.bootstrap.embedding_provider import ConfiguredEmbeddingProvider
from supportflow.identity.application.service import AuthService
from supportflow.identity.domain.models import Principal
from supportflow.identity.infrastructure.repository import (
    SqlAlchemySessionRepository,
    SqlAlchemyUserRepository,
)
from supportflow.identity.infrastructure.security import (
    Argon2PasswordHasher,
    SecureTokenSource,
)
from supportflow.knowledge.application.service import KnowledgeService
from supportflow.knowledge.infrastructure.embedding_providers import MockEmbeddingProvider
from supportflow.knowledge.infrastructure.repository import SqlAlchemyKnowledgeRepository
from supportflow.model.application.service import ModelConfigService
from supportflow.model.domain.gateway import ChatModelGateway
from supportflow.model.infrastructure.crypto import cipher_from_settings
from supportflow.model.infrastructure.factory import (
    GatewayResolver,
    available_model_modes,
    build_gateway_resolver,
)
from supportflow.model.infrastructure.repository import SqlAlchemyModelConfigRepository
from supportflow.shared.audit import AuditRecorder
from supportflow.shared.config import Settings, get_settings
from supportflow.shared.db import session_scope
from supportflow.shared.idempotency import IdempotencyStore
from supportflow.ticket.application.service import TicketService
from supportflow.ticket.domain.models import TicketCategory
from supportflow.ticket.infrastructure.repository import SqlAlchemyTicketRepository


@dataclass(frozen=True, slots=True)
class Services:
    settings: Settings
    session: Session
    auth: AuthService
    tickets: TicketService
    knowledge: KnowledgeService
    model_configs: ModelConfigService
    approvals: ActionApprovalService
    runs: RunService
    audit: AuditRecorder


def build_services(session: Session, settings: Settings | None = None) -> Services:
    cfg = settings or get_settings()
    token_source = SecureTokenSource()

    users = SqlAlchemyUserRepository(session)
    user_sessions = SqlAlchemySessionRepository(session)
    knowledge_repo = SqlAlchemyKnowledgeRepository(session)
    model_configs = build_model_config_service(session, cfg)
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
    available_modes = available_model_modes(
        chat_configured=model_configs.chat_capability_configured()
    )
    tickets = build_ticket_service(session, cfg)
    approvals = build_approval_service(session, tickets)
    runs = RunService(
        runs_repo,
        events_repo,
        steps_repo,
        tickets,
        IdempotencyStore(session),
        default_model_mode=cfg.model_mode,
        available_model_modes=available_modes,
    )
    knowledge = KnowledgeService(
        knowledge_repo,
        IdempotencyStore(session),
        build_embedding_provider(model_configs, cfg),
        upload_dir=cfg.upload_dir,
    )
    return Services(
        settings=cfg,
        session=session,
        auth=auth,
        tickets=tickets,
        knowledge=knowledge,
        model_configs=model_configs,
        approvals=approvals,
        runs=runs,
        audit=AuditRecorder(session),
    )


def build_model_config_service(session: Session, settings: Settings) -> ModelConfigService:
    """模型配置服务。

    ``cipher_from_settings`` 以工厂形式传入：主密钥未配置时，只有真正做加解密才失败，
    而不是让 mock 模式的整个容器起不来。
    """
    return ModelConfigService(
        SqlAlchemyModelConfigRepository(session),
        lambda: cipher_from_settings(settings),
        request_timeout_seconds=settings.model_request_timeout_seconds,
        max_attempts=settings.model_max_attempts,
    )


class TicketActionAdapter:
    """把 ticket 模块的用例适配成审批模块的 ``TicketActionPort``。

    **适配器放组合根**：审批模块因此不需要认识 ticket 模块（AGENTS.md §3）。
    授权仍在工单模块内完成 —— 这里只做转发，不做放行判断。
    """

    def __init__(self, tickets: TicketService) -> None:
        self._tickets = tickets

    def current_version(self, ticket_id: UUID) -> int | None:
        return self._tickets.current_version(ticket_id)

    def close_ticket(self, principal: Principal, *, ticket_id: UUID, expected_version: int) -> int:
        return self._tickets.close_ticket(principal, ticket_id, expected_version=expected_version)

    def transfer_ticket(
        self,
        principal: Principal,
        *,
        ticket_id: UUID,
        assignee_id: UUID,
        expected_version: int,
    ) -> int:
        return self._tickets.transfer_ticket(
            principal, ticket_id, assignee_id=assignee_id, expected_version=expected_version
        )


def build_ticket_service(session: Session, cfg: Settings) -> TicketService:
    """工单用例。模型配置决定「按次指定 real」是否被接受。"""
    model_configs = build_model_config_service(session, cfg)
    return TicketService(
        SqlAlchemyTicketRepository(session),
        IdempotencyStore(session),
        FirstRunScheduler(SqlAlchemyRunRepository(session)),
        default_model_mode=cfg.model_mode,
        available_model_modes=available_model_modes(
            chat_configured=model_configs.chat_capability_configured()
        ),
    )


class ApprovalProposalAdapter:
    """把审批用例适配成图里的 ``ActionProposalPort``。

    图只表达意图（动作 + 理由），参数不可变、工单版本校验与幂等复用都在审批模块。
    """

    def __init__(self, approvals: ActionApprovalService) -> None:
        self._approvals = approvals

    def propose(
        self, *, ticket_id: UUID, run_id: UUID, action_type: str, reason: str
    ) -> ActionProposalOutcome:
        """把审批模块的返回映射成 agent 域的结果类型。

        刻意在这里做映射而不是让审批模块返回 agent 的类型：那样会出现
        approval → agent 的反向依赖。
        """
        outcome = self._approvals.propose_by_system(
            ticket_id=ticket_id, run_id=run_id, action_type=action_type, reason=reason
        )
        return ActionProposalOutcome(
            request_id=UUID(str(outcome["request_id"])),
            action_type=str(outcome["action_type"]),
            expires_at=str(outcome["expires_at"]),
            replayed=bool(outcome["replayed"]),
        )


class RunOutcomeAdapter:
    """把审批结果推进到运行的终态。

    **幂等由状态判断保证**：只有运行仍处于 ``WAITING_APPROVAL`` 才迁移，
    因此重复决策、任务重投或检查点重放都不会产生第二笔效果。
    """

    def __init__(self, session: Session) -> None:
        self._runs = SqlAlchemyRunRepository(session)
        self._events = SqlAlchemyRunEventRepository(session)

    def complete_after_action(
        self, run_id: UUID, *, request_id: UUID, action_type: str
    ) -> None:
        if not self._is_waiting(run_id):
            return
        self._runs.finish(run_id, status=RunStatusEnum.COMPLETED)
        self._events.append(
            run_id,
            RunEventType.RUN_COMPLETED,
            {"via": "approval", "request_id": str(request_id), "action_type": action_type},
        )

    def hand_back(self, run_id: UUID, *, request_id: UUID, reason: str) -> None:
        if not self._is_waiting(run_id):
            return
        self._runs.finish(run_id, status=RunStatusEnum.NEEDS_HUMAN, error_code=reason)
        self._events.append(
            run_id,
            RunEventType.RUN_NEEDS_HUMAN,
            {"reason": reason, "request_id": str(request_id)},
        )

    def _is_waiting(self, run_id: UUID) -> bool:
        run = self._runs.find_by_id(run_id)
        return run is not None and run.status is RunStatusEnum.WAITING_APPROVAL


def build_approval_service(session: Session, tickets: TicketService) -> ActionApprovalService:
    """审批用例。工单能力通过适配器注入，且只暴露三个方法。"""
    return ActionApprovalService(
        SqlAlchemyActionRequestRepository(session),
        SqlAlchemyActionLedgerRepository(session),
        TicketActionAdapter(tickets),
        RunOutcomeAdapter(session),
    )


def build_embedding_provider(
    model_configs: ModelConfigService, cfg: Settings
) -> ConfiguredEmbeddingProvider:
    """构造知识模块的嵌入提供者。

    未启用 Embedding 配置时退回确定性 Mock（旧版索引版本）—— 这是「未配置」，
    不是「真实失败后的降级」。
    """
    return ConfiguredEmbeddingProvider(
        model_configs,
        fallback=MockEmbeddingProvider(),
        timeout_seconds=cfg.model_request_timeout_seconds,
    )


def build_gateway_resolver_for(
    cfg: Settings, model_configs: ModelConfigService
) -> GatewayResolver:
    """构造「运行模式 → 网关」的解析器。

    Mock 模式**不会**触碰密文，因此未配置主密钥也不影响本地开发与测试；
    real 模式则要求存在已启用且可解密的聊天配置，否则由 factory 直接失败。
    """
    return build_gateway_resolver(
        default_mode=cfg.model_mode,
        resolve_chat_config=model_configs.resolve_chat_config,
    )


@contextmanager
def services_scope(settings: Settings | None = None) -> Iterator[Services]:
    """请求级依赖：一个 Session 对应一个 HTTP 请求的完整事务。"""
    with session_scope() as session:
        yield build_services(session, settings)


# --- Worker 用 -----------------------------------------------------------------


class TicketFactsAdapter:
    """把 ``ticket`` 仓储收敛成 agent 需要的两个能力。

    agent 只应看到「工单事实」与「写入分类」，而不是整个工单仓储 —— 见 AGENTS.md §3。
    """

    def __init__(self, repository: SqlAlchemyTicketRepository) -> None:
        self._repository = repository

    def facts(self, ticket_id: UUID) -> TicketFacts | None:
        ticket = self._repository.find_by_id(ticket_id)
        if ticket is None:
            return None
        return TicketFacts(
            ticket_id=ticket.id,
            ticket_no=ticket.ticket_no,
            subject=ticket.subject,
            body_cleaned=ticket.body_cleaned,
            clean_version=ticket.clean_version,
            status=ticket.status.value,
        )

    def assign_category(self, ticket_id: UUID, category: TicketCategory) -> None:
        self._repository.assign_category(ticket_id, category)


class RetrievalAdapter:
    """把 ``KnowledgeService`` 的内部检索入口映射为 agent 侧的 ``Evidence``。"""

    def __init__(self, knowledge: KnowledgeService) -> None:
        self._knowledge = knowledge

    def retrieve_for_run(self, query: str, *, limit: int) -> list[Evidence]:
        return [
            Evidence(
                source_type=item.citation.source_type.value,
                source_id=str(item.citation.source_id),
                source_version=item.citation.source_version,
                chunk_id=str(item.citation.chunk_id) if item.citation.chunk_id else None,
                locator=item.citation.locator,
                quote_text=item.citation.quote_text,
                rank_no=item.citation.rank_no,
                score=item.citation.score,
                full_text_rank=item.full_text_rank,
                vector_rank=item.vector_rank,
            )
            for item in self._knowledge.retrieve_for_run(query, limit=limit)
        ]


def build_execution_unit(
    session: Session,
    *,
    settings: Settings | None = None,
    gateway: ChatModelGateway | None = None,
    gateway_for: GatewayResolver | None = None,
    retrieval: KnowledgeRetrievalPort | None = None,
) -> RunExecutionUnit:
    """装配一次运行所需的协作者。

    ``gateway`` 注入固定替身（测试常用，对所有模式返回同一个网关）；
    ``gateway_for`` 注入按运行模式解析的解析器；两者都不给则按部署配置解析。
    ``retrieval`` 同样可注入替身，便于在不接触真实模型的前提下验证状态图行为。
    """
    cfg = settings or get_settings()
    runs_repo = SqlAlchemyRunRepository(session)
    model_configs = build_model_config_service(session, cfg)
    tickets = build_ticket_service(session, cfg)
    approvals = build_approval_service(session, tickets)
    knowledge = KnowledgeService(
        SqlAlchemyKnowledgeRepository(session),
        IdempotencyStore(session),
        build_embedding_provider(model_configs, cfg),
        upload_dir=cfg.upload_dir,
    )
    if gateway_for is None:
        if gateway is not None:
            gateway_for = lambda _mode: gateway  # noqa: E731 - 固定替身
        else:
            gateway_for = build_gateway_resolver_for(cfg, model_configs)

    executor = RunExecutor(
        gateway_for=gateway_for,
        retrieval=retrieval or RetrievalAdapter(knowledge),
        actions=ApprovalProposalAdapter(approvals),
        tickets=TicketFactsAdapter(SqlAlchemyTicketRepository(session)),
        runs=runs_repo,
        events=SqlAlchemyRunEventRepository(session),
        steps=SqlAlchemyRunStepRepository(session),
        database_url=cfg.database_url,
        # 每个图节点一个事务边界：崩溃时该节点的写入整体回滚，重放不留半成品。
        commit=session.commit,
        max_attempts=cfg.model_max_attempts,
        # 检查点实现由组合根注入，避免 application 层反向依赖 infrastructure 层。
        checkpointer_factory=postgres_checkpointer,
        config_for_run=checkpoint_config,
        base_delay_seconds=0.5,
    )
    return RunExecutionUnit(runs=runs_repo, executor=executor)


@contextmanager
def execution_unit_scope(settings: Settings | None = None) -> Iterator[RunExecutionUnit]:
    """为 Worker 组装一次执行所需的协作者（独立事务）。"""
    cfg = settings or get_settings()
    with session_scope() as session:
        yield build_execution_unit(session, settings=cfg)


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
