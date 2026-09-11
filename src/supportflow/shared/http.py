"""跨模块共用的 HTTP 层构件：请求 ID、幂等键、分页参数。"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Header, Query, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from supportflow.shared.errors import InvalidRequest

IDEMPOTENCY_HEADER = "Idempotency-Key"
MIN_IDEMPOTENCY_KEY_LENGTH = 8


def idempotency_key(
    value: Annotated[str | None, Header(alias=IDEMPOTENCY_HEADER)] = None,
) -> str:
    """所有有副作用的写接口都必须携带。缺失或过短一律 400。"""
    if value is None or len(value.strip()) < MIN_IDEMPOTENCY_KEY_LENGTH:
        raise InvalidRequest(
            f"请求头 {IDEMPOTENCY_HEADER} 必填，且长度不得少于 "
            f"{MIN_IDEMPOTENCY_KEY_LENGTH} 个字符"
        )
    return value.strip()


class RequestIdMiddleware(BaseHTTPMiddleware):
    """为每个请求确定 ``request_id``：优先沿用调用方传入的同名请求头。

    请求 ID 会回写到响应头，并进入所有 Problem Details 响应体。
    """

    def __init__(self, app: object, *, header_name: str = "X-Request-Id") -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._header_name = header_name

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get(self._header_name)
        request_id = incoming.strip() if incoming and incoming.strip() else uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[self._header_name] = request_id
        return response


def pagination(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> tuple[int, int]:
    return limit, offset
