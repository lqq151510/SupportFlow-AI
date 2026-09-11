"""接口层的公共依赖：装配容器、解析调用者、校验 CSRF、角色判定。"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Request

from supportflow.bootstrap.container import Services, services_scope
from supportflow.identity.domain.models import Principal
from supportflow.shared.errors import Forbidden


def get_services() -> Iterator[Services]:
    """请求级服务容器。同一个请求内 FastAPI 会缓存本依赖，因此 Session 唯一。

    注意：依赖的退出代码（提交事务）在响应生成之后执行；异常时由 ``session_scope``
    回滚并把异常交给统一错误处理，不会留下半提交状态。
    """
    with services_scope() as services:
        yield services


def _session_cookie(request: Request, services: Services) -> str | None:
    return request.cookies.get(services.settings.session_cookie_name)


def current_principal(
    request: Request, services: Services = Depends(get_services)
) -> Principal:
    return services.auth.resolve_principal(_session_cookie(request, services))


def csrf_protected_principal(
    request: Request, services: Services = Depends(get_services)
) -> Principal:
    """所有写请求都应使用本依赖：先校验 CSRF，再解析调用者。"""
    token = _session_cookie(request, services)
    services.auth.verify_csrf(token, request.headers.get(services.settings.csrf_header_name))
    return services.auth.resolve_principal(token)


def require_staff(principal: Principal = Depends(current_principal)) -> Principal:
    if not principal.is_staff:
        raise Forbidden("需要坐席或管理员权限")
    return principal


def require_admin(principal: Principal = Depends(current_principal)) -> Principal:
    if not principal.is_admin:
        raise Forbidden("需要管理员权限")
    return principal
