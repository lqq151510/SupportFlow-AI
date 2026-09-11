"""RFC 9457 Problem Details 与稳定错误码。

对外错误一律携带稳定的 ``code`` 与 ``request_id``；底层异常文本不暴露给客户端。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

PROBLEM_MEDIA_TYPE = "application/problem+json"


class ProblemDetail(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    code: str
    request_id: str


class AppError(Exception):
    """全部业务错误的基类。子类通过类属性声明状态码与稳定错误码。"""

    status: int = 500
    code: str = "internal_error"
    title: str = "服务器内部错误"

    def __init__(self, detail: str | None = None, **extra: Any) -> None:
        super().__init__(detail or self.title)
        self.detail = detail
        self.extra = extra


class InvalidRequest(AppError):
    status = 400
    code = "invalid_request"
    title = "请求不合法"


class ValidationFailed(AppError):
    """请求体/参数不符合契约。状态码沿用 FastAPI 的 422 约定。"""

    status = 422
    code = "validation_failed"
    title = "请求参数校验失败"


class Unauthenticated(AppError):
    status = 401
    code = "unauthenticated"
    title = "未登录或会话已失效"


class Forbidden(AppError):
    status = 403
    code = "forbidden"
    title = "无权访问该资源"


class CsrfValidationFailed(Forbidden):
    code = "csrf_failed"
    title = "CSRF 校验失败"


class NotFound(AppError):
    status = 404
    code = "not_found"
    title = "资源不存在"


class Conflict(AppError):
    status = 409
    code = "conflict"
    title = "请求与当前资源状态冲突"


class IdempotencyKeyReused(Conflict):
    code = "idempotency_key_reused"
    title = "幂等键已用于不同的请求"


class RunAlreadyActive(Conflict):
    code = "run_already_active"
    title = "该工单已有活动中的运行"


class ModelModeNotPermitted(Forbidden):
    code = "model_mode_not_permitted"
    title = "当前角色不允许指定运行模式"


class ModelModeUnavailable(Conflict):
    """按次指定的模式在当前构建里没有对应网关。

    刻意返回错误而不是降级执行：否则运行会被标记为 ``real`` 却由 Mock 产出，
    评测数据即失真。
    """

    code = "model_mode_unavailable"
    title = "当前部署不支持该运行模式"


class ModelUnavailable(AppError):
    status = 503
    code = "model_unavailable"
    title = "模型服务暂时不可用"


class ModelResponseInvalid(AppError):
    status = 502
    code = "model_response_invalid"
    title = "模型返回内容不符合约定结构"


class ServiceUnavailable(AppError):
    status = 503
    code = "service_unavailable"
    title = "依赖服务不可用"


def request_id_of(request: Request) -> str:
    return str(getattr(request.state, "request_id", "-"))


def build_problem(exc: AppError, request: Request) -> ProblemDetail:
    return ProblemDetail(
        title=exc.title,
        status=exc.status,
        detail=exc.detail,
        instance=request.url.path,
        code=exc.code,
        request_id=request_id_of(request),
    )


def problem_response(exc: AppError, request: Request) -> JSONResponse:
    payload = build_problem(exc, request).model_dump(exclude_none=True)
    payload.update(exc.extra)
    return JSONResponse(status_code=exc.status, content=payload, media_type=PROBLEM_MEDIA_TYPE)


def install_error_handlers(app: FastAPI) -> None:
    """注册统一错误处理。未捕获异常只返回通用信息，细节仅进日志。"""

    @app.exception_handler(AppError)
    def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        if exc.status >= 500:
            logger.error("app error", extra={"code": exc.code, "detail": exc.detail})
        return problem_response(exc, request)

    @app.exception_handler(RequestValidationError)
    def _handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """把 FastAPI 默认的 ``{"detail": [...]}`` 也收敛成 Problem Details。

        否则客户端要在两种错误结构之间分支 —— 契约一致性比复用框架默认值重要。
        """
        problem = ValidationFailed("请求参数不符合接口契约")
        problem.extra["errors"] = [
            {
                "location": list(error.get("loc", ())),
                "message": error.get("msg", ""),
                "type": error.get("type", ""),
            }
            for error in exc.errors()
        ]
        return problem_response(problem, request)

    @app.exception_handler(Exception)
    def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error", extra={"path": request.url.path})
        return problem_response(
            AppError("处理请求时发生未预期的错误"),
            request,
        )
