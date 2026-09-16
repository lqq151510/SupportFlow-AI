"""FastAPI 装配。

这是唯一把各模块 ``api`` 路由挂到同一个 Web 应用上的地方。路由前缀统一为
``/api/v1``，只有 ``/healthz`` 例外（供容器编排探活，不参与版本化）。

启动期只做一件事：确保 ``run_events`` 的当月与未来分区存在。**建表由 Alembic
负责**，不在应用启动时自动建表 —— 否则生产环境会绕过迁移审计。
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from supportflow.agent.api.routes import runs_router, ticket_runs_router
from supportflow.approval.api.routes import router as action_request_router
from supportflow.bootstrap.container import prepare_database
from supportflow.evaluation.api.routes import router as evaluation_router
from supportflow.identity.api.routes import router as identity_router
from supportflow.knowledge.api.routes import history_router
from supportflow.knowledge.api.routes import router as knowledge_router
from supportflow.model.api.routes import router as model_config_router
from supportflow.shared.config import Settings, get_settings
from supportflow.shared.errors import install_error_handlers
from supportflow.shared.http import RequestIdMiddleware
from supportflow.shared.logging import configure_logging
from supportflow.ticket.api.routes import router as ticket_router

API_PREFIX = "/api/v1"

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    logger.info(
        "启动 %s：model_mode=%s", settings.app_name, settings.model_mode
    )
    # 数据库不可达时**直接失败**，不进入「服务已就绪但请求全 500」的状态。
    created = prepare_database()
    if created:
        logger.info("已创建运行事件分区: %s", ", ".join(created))
    yield
    logger.info("已停止 %s", settings.app_name)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="SupportFlow Agent · 单工作区电商售后工单助手",
        lifespan=lifespan,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url="/docs",
        redoc_url=None,
    )
    app.state.settings = settings

    app.add_middleware(RequestIdMiddleware, header_name=settings.request_id_header)
    install_error_handlers(app)

    api = APIRouter(prefix=API_PREFIX)
    api.include_router(identity_router)
    api.include_router(ticket_router)
    api.include_router(knowledge_router)
    api.include_router(history_router)
    api.include_router(model_config_router)
    api.include_router(action_request_router)
    api.include_router(evaluation_router)
    api.include_router(ticket_runs_router)
    api.include_router(runs_router)
    app.include_router(api)

    @app.get("/healthz", tags=["ops"], summary="存活探针")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "model_mode": settings.model_mode}

    return app


app = create_app()
