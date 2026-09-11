"""身份应用服务：登录、按会话解析调用者、CSRF 校验、登出。

本模块只依赖领域端口，具体实现由 ``bootstrap.container`` 注入。
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from supportflow.identity.domain.models import (
    IssuedSession,
    Principal,
    User,
    UserStatus,
)
from supportflow.identity.domain.ports import (
    PasswordHasherPort,
    SessionRepositoryPort,
    TokenSourcePort,
    UserRepositoryPort,
)
from supportflow.shared.errors import CsrfValidationFailed, Forbidden, Unauthenticated


@dataclass(frozen=True, slots=True)
class LoginResult:
    principal: Principal
    session: IssuedSession


def _principal_of(user: User) -> Principal:
    return Principal(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
    )


class AuthService:
    def __init__(
        self,
        users: UserRepositoryPort,
        sessions: SessionRepositoryPort,
        hasher: PasswordHasherPort,
        tokens: TokenSourcePort,
        *,
        session_ttl_seconds: int,
    ) -> None:
        self._users = users
        self._sessions = sessions
        self._hasher = hasher
        self._tokens = tokens
        self._ttl = session_ttl_seconds

    def login(
        self,
        email: str,
        password: str,
        *,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> LoginResult:
        user = self._users.find_by_email(email)
        if user is None or not self._hasher.verify(user.password_hash, password):
            # 不区分「用户不存在」与「口令错误」，避免账号枚举。
            raise Unauthenticated("邮箱或密码不正确")
        if user.status is not UserStatus.ACTIVE:
            # 能走到这里说明口令已验证通过，因此不构成账号枚举风险。
            raise Forbidden("账号已停用，请联系管理员")

        now = datetime.now(UTC)
        token = self._tokens.new_session_token()
        csrf_token = self._tokens.new_csrf_token()
        expires_at = now + timedelta(seconds=self._ttl)
        self._sessions.create(
            user_id=user.id,
            token_hash=self._tokens.digest(token),
            csrf_hash=self._tokens.digest(csrf_token),
            expires_at=expires_at,
            ip=ip,
            user_agent=user_agent,
        )
        self._users.touch_last_login(user.id, now)
        return LoginResult(
            principal=_principal_of(user),
            session=IssuedSession(token=token, csrf_token=csrf_token, expires_at=expires_at),
        )

    def resolve_principal(self, session_token: str | None) -> Principal:
        """按服务端会话解析调用者。这是角色与用户标识的唯一来源。"""
        if not session_token:
            raise Unauthenticated("缺少会话 Cookie")
        record = self._sessions.find(self._tokens.digest(session_token))
        if record is None or not record.is_usable(datetime.now(UTC)):
            raise Unauthenticated("会话已失效，请重新登录")
        user = self._users.find_by_id(record.user_id)
        if user is None or user.status is not UserStatus.ACTIVE:
            raise Unauthenticated("会话对应的账号不可用")
        return _principal_of(user)

    def verify_csrf(self, session_token: str | None, csrf_token: str | None) -> None:
        """所有写请求都必须通过。失败一律返回 403 csrf_failed。"""
        if not session_token or not csrf_token:
            raise CsrfValidationFailed("缺少会话或 CSRF 令牌")
        record = self._sessions.find(self._tokens.digest(session_token))
        if record is None:
            raise CsrfValidationFailed("会话不存在")
        if not hmac.compare_digest(record.csrf_hash, self._tokens.digest(csrf_token)):
            raise CsrfValidationFailed("CSRF 令牌不匹配")

    def logout(self, session_token: str | None) -> None:
        if session_token:
            self._sessions.revoke(self._tokens.digest(session_token), datetime.now(UTC))
