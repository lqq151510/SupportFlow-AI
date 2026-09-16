"""Agent 运行接口与 SSE 事件流。

两段式协议（PLAN.md 已锁定）：
写接口（提交工单 / 手动发起运行）只负责把运行**入队**并立刻返回 ``run_id``；
运行进度通过独立的 ``GET /runs/{run_id}/events`` 事件流获取，断线后用
``Last-Event-ID`` 续传，服务端不会因此重新生成或重复写入事件。

SSE 实现说明：生成器是**同步**的，内部只做阻塞式数据库轮询。Starlette 会在
线程池中逐次推进生成器，因此不会阻塞事件循环；代价是每条活跃连接在休眠期间
占用一个线程池工作线程。阶段 3 若需要放大并发，应改为 ``LISTEN/NOTIFY`` 长轮询
而不是继续缩短轮询间隔。
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse

from supportflow.agent.api.schemas import RunListOut, RunOut, StartRunRequest
from supportflow.agent.domain.models import RunEvent, RunStatus
from supportflow.bootstrap.container import (
    Services,
    authorize_run_access,
    current_run_status,
    poll_run_events,
)
from supportflow.identity.api.dependencies import (
    csrf_protected_principal,
    current_principal,
    get_services,
)
from supportflow.identity.domain.models import Principal
from supportflow.shared.config import Settings, get_settings
from supportflow.shared.errors import InvalidRequest, request_id_of
from supportflow.shared.http import idempotency_key

SSE_MEDIA_TYPE = "text/event-stream"
LAST_EVENT_ID_HEADER = "Last-Event-ID"

ticket_runs_router = APIRouter(prefix="/tickets", tags=["runs"])
runs_router = APIRouter(prefix="/runs", tags=["runs"])


# --- 运行查询与人工重试 ---------------------------------------------------------


@ticket_runs_router.post("/{ticket_id}/runs", status_code=202, response_model=RunOut)
def start_run(
    ticket_id: UUID,
    payload: StartRunRequest,
    request: Request,
    response: Response,
    principal: Principal = Depends(csrf_protected_principal),
    services: Services = Depends(get_services),
    idempotency: str = Depends(idempotency_key),
) -> RunOut:
    """人工发起一次新运行（不复活旧运行）。非坐席一律 403。"""
    run = services.runs.start_new_run(
        principal,
        ticket_id,
        idempotency_key=idempotency,
        model_mode=payload.model_mode,
    )
    services.audit.record(
        action="run.started_by_human",
        actor_id=principal.user_id,
        resource_type="agent_run",
        resource_id=str(run.id),
        request_id=request_id_of(request),
        details={"ticket_id": str(run.ticket_id), "model_mode": run.model_mode},
    )
    response.headers["Location"] = f"/api/v1/runs/{run.id}"
    return RunOut.of(run)


@ticket_runs_router.get("/{ticket_id}/runs", response_model=RunListOut)
def list_runs(
    ticket_id: UUID,
    principal: Principal = Depends(current_principal),
    services: Services = Depends(get_services),
) -> RunListOut:
    runs = services.runs.list_runs(principal, ticket_id)
    return RunListOut(items=[RunOut.of(run) for run in runs])


@runs_router.get("/{run_id}", response_model=RunOut)
def get_run(
    run_id: UUID,
    principal: Principal = Depends(current_principal),
    services: Services = Depends(get_services),
) -> RunOut:
    return RunOut.of(services.runs.get_run(principal, run_id))


# --- SSE 事件流 -----------------------------------------------------------------


def _resolve_cursor(request: Request, after: int) -> int:
    """合并 ``?after=`` 与 ``Last-Event-ID``，取较新者。

    ``EventSource`` 在重连时会自动带上 ``Last-Event-ID``；显式查询参数则便于
    ``curl`` 与集成测试复现某一时刻之后的增量。
    """
    raw = request.headers.get(LAST_EVENT_ID_HEADER)
    if raw is None or not raw.strip():
        return after
    try:
        parsed = int(raw.strip())
    except ValueError as exc:
        raise InvalidRequest(f"请求头 {LAST_EVENT_ID_HEADER} 必须是整数") from exc
    if parsed < 0:
        raise InvalidRequest(f"请求头 {LAST_EVENT_ID_HEADER} 不能为负数")
    return max(after, parsed)


def _event_frame(event: RunEvent) -> str:
    data = json.dumps(
        {
            # 数据帧属于 JSON 契约，主键统一字符串化；SSE 帧头的 ``id:`` 保持
            # 数字游标，供 Last-Event-ID 续传和数据库范围查询使用。
            "id": str(event.id),
            "run_id": str(event.run_id),
            "type": event.event_type.value,
            "payload": event.payload,
            "created_at": event.created_at.isoformat(),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return f"id: {event.id}\nevent: {event.event_type.value}\ndata: {data}\n\n"


def _closed_frame(status: RunStatus | None, *, reason: str) -> str:
    """通知前端本次流已结束及原因，避免客户端无谓地反复重连。"""
    data = json.dumps(
        {"status": status.value if status else None, "reason": reason},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"event: stream.closed\ndata: {data}\n\n"


def _event_stream(run_id: UUID, after_id: int, settings: Settings) -> Iterator[str]:
    yield f"retry: {settings.sse_retry_ms}\n\n"

    cursor = after_id
    deadline = time.monotonic() + settings.sse_max_duration_seconds
    idle_polls = 0

    while True:
        pending = poll_run_events(run_id, after_id=cursor)
        if pending:
            idle_polls = 0
            for event in pending:
                cursor = event.id
                yield _event_frame(event)
        else:
            idle_polls += 1
            if idle_polls >= settings.sse_heartbeat_polls:
                idle_polls = 0
                # 注释帧：不是事件，前端不会触发监听器，仅用于穿透代理的空闲超时。
                yield ": keep-alive\n\n"

        status = current_run_status(run_id)
        if status is None or status.is_terminal:
            # 状态与事件分属不同事务读；终态后再补读一次，避免尾部事件被漏掉。
            for event in poll_run_events(run_id, after_id=cursor):
                cursor = event.id
                yield _event_frame(event)
            yield _closed_frame(status, reason="terminal")
            return

        if time.monotonic() >= deadline:
            yield _closed_frame(status, reason="timeout")
            return

        time.sleep(settings.sse_poll_interval_seconds)


@runs_router.get("/{run_id}/events")
def stream_run_events(
    run_id: UUID,
    request: Request,
    after: int = Query(default=0, ge=0, description="仅推送 id 大于该值的事件"),
) -> StreamingResponse:
    settings = get_settings()
    cursor = _resolve_cursor(request, after)
    session_token = request.cookies.get(settings.session_cookie_name)

    # 鉴权必须在返回响应**之前**完成：生成器内部抛出的异常发生在响应头已发送之后，
    # 客户端只会拿到 200 加一条被截断的流，而拿不到 401/404。
    authorize_run_access(session_token, run_id)

    return StreamingResponse(
        _event_stream(run_id, cursor, settings),
        media_type=SSE_MEDIA_TYPE,
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            # 告诉 nginx 不要缓冲，否则事件会被攒到流结束才下发。
            "X-Accel-Buffering": "no",
        },
    )
