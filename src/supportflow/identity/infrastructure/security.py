"""身份模块的安全原语：口令哈希与会话令牌签发。

会话令牌只以 SHA-256 摘要落库；CSRF 令牌同样只保存摘要。
原始值仅在签发那一刻返回给调用方，之后无法从数据库还原。
"""

from __future__ import annotations

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_SESSION_TOKEN_BYTES = 32
_CSRF_TOKEN_BYTES = 24


class Argon2PasswordHasher:
    def __init__(self) -> None:
        self._hasher = PasswordHasher()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False


class SecureTokenSource:
    def new_session_token(self) -> str:
        return secrets.token_urlsafe(_SESSION_TOKEN_BYTES)

    def new_csrf_token(self) -> str:
        return secrets.token_urlsafe(_CSRF_TOKEN_BYTES)

    def digest(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
