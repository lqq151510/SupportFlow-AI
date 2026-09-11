"""身份接口。

Cookie 策略（见 PLAN.md「服务端会话、HttpOnly Cookie 和写请求 CSRF 校验」）：

* 会话 Cookie：``HttpOnly`` + ``SameSite``，前端 JS 不可读。
* CSRF Cookie：**故意**不设 ``HttpOnly``，前端读取后回填到 ``X-CSRF-Token`` 请求头；
  服务端只保存它的摘要，比较时使用恒定时间比较。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request, Response

from supportflow.bootstrap.container import Services
from supportflow.identity.api.dependencies import (
    csrf_protected_principal,
    current_principal,
    get_services,
)
from supportflow.identity.api.schemas import LoginRequest, PrincipalOut
from supportflow.identity.domain.models import IssuedSession, Principal
from supportflow.shared.errors import request_id_of

router = APIRouter(tags=["identity"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _set_auth_cookies(response: Response, services: Services, session: IssuedSession) -> None:
    cfg = services.settings
    max_age = max(0, int((session.expires_at - datetime.now(UTC)).total_seconds()))
    common: dict[str, Any] = {
        "max_age": max_age,
        "secure": cfg.cookie_secure,
        "samesite": cfg.cookie_samesite,
        "path": "/",
    }
    response.set_cookie(cfg.session_cookie_name, session.token, httponly=True, **common)
    # CSRF Cookie 必须可被前端读取，因此不设 HttpOnly。
    response.set_cookie(cfg.csrf_cookie_name, session.csrf_token, httponly=False, **common)


def _clear_auth_cookies(response: Response, services: Services) -> None:
    cfg = services.settings
    response.delete_cookie(cfg.session_cookie_name, path="/")
    response.delete_cookie(cfg.csrf_cookie_name, path="/")


@router.post("/auth/login", response_model=PrincipalOut)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    services: Services = Depends(get_services),
) -> PrincipalOut:
    result = services.auth.login(
        payload.email,
        payload.password,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    _set_auth_cookies(response, services, result.session)
    services.audit.record(
        action="auth.login",
        actor_id=result.principal.user_id,
        resource_type="user",
        resource_id=str(result.principal.user_id),
        request_id=request_id_of(request),
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        details={"role": result.principal.role.value},
    )
    return PrincipalOut.of(result.principal)


@router.post("/auth/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    principal: Principal = Depends(csrf_protected_principal),
    services: Services = Depends(get_services),
) -> Response:
    services.auth.logout(request.cookies.get(services.settings.session_cookie_name))
    services.audit.record(
        action="auth.logout",
        actor_id=principal.user_id,
        resource_type="user",
        resource_id=str(principal.user_id),
        request_id=request_id_of(request),
    )
    _clear_auth_cookies(response, services)
    response.status_code = 204
    return response


@router.get("/auth/me", response_model=PrincipalOut)
def me(principal: Principal = Depends(current_principal)) -> PrincipalOut:
    return PrincipalOut.of(principal)
