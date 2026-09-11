"""身份模块的领域端口。

端口只使用领域类型，不允许出现 ``Session`` 或其他基础设施类型；
具体实现位于 ``identity.infrastructure``。
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from supportflow.identity.domain.models import NewUser, SessionRecord, User


class UserRepositoryPort(Protocol):
    def find_by_email(self, email: str) -> User | None: ...

    def find_by_id(self, user_id: UUID) -> User | None: ...

    def add(self, new_user: NewUser) -> User: ...

    def touch_last_login(self, user_id: UUID, at: datetime) -> None: ...


class SessionRepositoryPort(Protocol):
    def create(
        self,
        *,
        user_id: UUID,
        token_hash: str,
        csrf_hash: str,
        expires_at: datetime,
        ip: str | None,
        user_agent: str | None,
    ) -> None: ...

    def find(self, token_hash: str) -> SessionRecord | None: ...

    def revoke(self, token_hash: str, at: datetime) -> None: ...


class PasswordHasherPort(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password_hash: str, password: str) -> bool: ...


class TokenSourcePort(Protocol):
    """会话令牌与 CSRF 令牌的生成与摘要。"""

    def new_session_token(self) -> str: ...

    def new_csrf_token(self) -> str: ...

    def digest(self, value: str) -> str: ...
