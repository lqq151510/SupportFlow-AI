"""身份域模型。

纯业务类型，不导入 FastAPI、SQLAlchemy 或任何基础设施库。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class Role(StrEnum):
    USER = "USER"
    AGENT = "AGENT"
    ADMIN = "ADMIN"

    @property
    def is_staff(self) -> bool:
        """坐席与管理员可以处理工作区全部工单。"""
        return self in (Role.AGENT, Role.ADMIN)


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    email: str
    display_name: str
    role: Role
    status: UserStatus
    password_hash: str
    last_login_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class NewUser:
    email: str
    display_name: str
    role: Role
    password_hash: str


@dataclass(frozen=True, slots=True)
class Principal:
    """由服务端会话解析出的调用者身份。

    角色与用户标识**只能**来自这里。普通接口不得接受客户端传入的 ``role``、
    ``user_id`` 或 ``assignee_id`` —— 见 AGENTS.md §4。
    """

    user_id: UUID
    email: str
    display_name: str
    role: Role

    @property
    def is_staff(self) -> bool:
        return self.role.is_staff

    @property
    def is_admin(self) -> bool:
        return self.role is Role.ADMIN


@dataclass(frozen=True, slots=True)
class IssuedSession:
    """登录成功后签发的凭据。原始令牌仅在此刻可见，服务端只保存哈希。"""

    token: str
    csrf_token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class SessionRecord:
    """服务端会话的持久化视图（不含原始令牌）。"""

    user_id: UUID
    csrf_hash: str
    expires_at: datetime
    revoked_at: datetime | None

    def is_usable(self, now: datetime) -> bool:
        return self.revoked_at is None and self.expires_at > now
