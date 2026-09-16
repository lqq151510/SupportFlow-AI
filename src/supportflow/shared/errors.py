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
        #: 上游返回的原始诊断信息。
        #:
        #: **刻意不放进 ``extra``** —— ``extra`` 会被 ``problem_response`` 合并进响应体，
        #: 而 AGENTS.md §8 要求不把底层异常文本暴露给客户端。需要用它的只有
        #: 管理员专用的连接测试路径，那里显式读取本属性。
        self.upstream_message: str | None = None


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


class ModelAuthenticationFailed(AppError):
    """上游拒绝我们的凭据：**不重试**。

    参数与权限错误重试多少次都是同样的结果，只会放大限流与延迟 —— 见 AGENTS.md §5。
    """

    status = 502
    code = "model_auth_failed"
    title = "模型服务拒绝了当前凭据"


class ModelRequestRejected(AppError):
    """上游因请求本身（模型名、参数、额度）拒绝：**不重试**。"""

    status = 502
    code = "model_request_rejected"
    title = "模型服务拒绝了该请求"


class ModelConfigInvalid(AppError):
    """模型配置不可用或未配置完整（例如缺少主密钥、未启用任何聊天配置）。"""

    status = 503
    code = "model_config_invalid"
    title = "模型配置不可用"


class ActionRequestNotFound(NotFound):
    code = "action_request_not_found"
    title = "操作申请不存在"


class ActionRequestNotPending(Conflict):
    """申请已被处理（批准/拒绝/过期）。

    重复审批必须返回稳定错误码而不是静默成功 —— 否则调用方无法区分
    「我的审批生效了」与「别人已经处理过了」。
    """

    code = "action_request_not_pending"
    title = "该操作申请已被处理"


class ActionRequestExpired(Conflict):
    """审批过期不可执行（PLAN §5；AGENTS.md §8 要求有稳定的过期错误码）。"""

    code = "action_request_expired"
    title = "操作申请已过期"


class TicketAlreadyClosed(Conflict):
    """CLOSED 是终态，不允许再次关闭（AGENTS.md §8：状态迁移非法要有稳定错误码）。"""

    code = "ticket_already_closed"
    title = "工单已关闭"


class TicketVersionChanged(Conflict):
    """工单在申请之后被改动过，因此不执行该动作。

    保存「工单版本」的意义就在这里：审批针对的是**申请人看到的那一版工单**，
    版本一变，授权的前提就不成立了。
    """

    code = "ticket_version_changed"
    title = "工单已变更，请重新发起申请"


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
    # 5xx 的 detail 往往来自上游、驱动或不可信输入。客户端只需要稳定 code 和
    # request_id 来关联服务端诊断，不能据此获知内部实现细节。
    detail = exc.detail if exc.status < 500 else None
    return ProblemDetail(
        title=exc.title,
        status=exc.status,
        detail=detail,
        instance=request.url.path,
        code=exc.code,
        request_id=request_id_of(request),
    )


def problem_response(exc: AppError, request: Request) -> JSONResponse:
    payload = build_problem(exc, request).model_dump(exclude_none=True)
    # 对 5xx 同样不合并额外字段，防止调用方误把上游诊断放入 ``extra`` 后外泄。
    if exc.status < 500:
        payload.update(exc.extra)
    return JSONResponse(status_code=exc.status, content=payload, media_type=PROBLEM_MEDIA_TYPE)


def install_error_handlers(app: FastAPI) -> None:
    """注册统一错误处理。未捕获异常只返回通用信息，细节仅进日志。"""

    @app.exception_handler(AppError)
    def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        if exc.status >= 500:
            # ``detail`` 可能来自上游或不可信输入。即使当前 formatter 不渲染 extra，
            # 也不能把它附在 LogRecord 上，以免切换结构化日志后意外泄漏。
            logger.error(
                "app error",
                extra={"code": exc.code, "request_id": request_id_of(request)},
            )
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
