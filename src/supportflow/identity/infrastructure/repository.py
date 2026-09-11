"""身份模块的持久化实现。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from supportflow.identity.domain.models import (
    NewUser,
    Role,
    SessionRecord,
    User,
    UserStatus,
)
from supportflow.identity.infrastructure.tables import UserRow, UserSessionRow


def _to_user(row: UserRow) -> User:
    return User(
        id=row.id,
        email=row.email,
        display_name=row.display_name,
        role=Role(row.role),
        status=UserStatus(row.status),
        password_hash=row.password_hash,
        last_login_at=row.last_login_at,
    )


class SqlAlchemyUserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_email(self, email: str) -> User | None:
        row = self._session.scalars(
            select(UserRow).where(UserRow.email == email.strip().lower())
        ).one_or_none()
        return _to_user(row) if row else None

    def find_by_id(self, user_id: UUID) -> User | None:
        row = self._session.get(UserRow, user_id)
        return _to_user(row) if row else None

    def add(self, new_user: NewUser) -> User:
        row = UserRow(
            email=new_user.email.strip().lower(),
            display_name=new_user.display_name,
            role=new_user.role.value,
            status=UserStatus.ACTIVE.value,
            password_hash=new_user.password_hash,
        )
        self._session.add(row)
        self._session.flush()
        return _to_user(row)

    def touch_last_login(self, user_id: UUID, at: datetime) -> None:
        self._session.execute(
            update(UserRow).where(UserRow.id == user_id).values(last_login_at=at)
        )


class SqlAlchemySessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        user_id: UUID,
        token_hash: str,
        csrf_hash: str,
        expires_at: datetime,
        ip: str | None,
        user_agent: str | None,
    ) -> None:
        self._session.add(
            UserSessionRow(
                user_id=user_id,
                token_hash=token_hash,
                csrf_hash=csrf_hash,
                expires_at=expires_at,
                ip=ip,
                user_agent=(user_agent or "")[:400] or None,
            )
        )
        self._session.flush()

    def find(self, token_hash: str) -> SessionRecord | None:
        row = self._session.scalars(
            select(UserSessionRow).where(UserSessionRow.token_hash == token_hash)
        ).one_or_none()
        if row is None:
            return None
        return SessionRecord(
            user_id=row.user_id,
            csrf_hash=row.csrf_hash,
            expires_at=row.expires_at,
            revoked_at=row.revoked_at,
        )

    def revoke(self, token_hash: str, at: datetime) -> None:
        self._session.execute(
            update(UserSessionRow)
            .where(UserSessionRow.token_hash == token_hash, UserSessionRow.revoked_at.is_(None))
            .values(revoked_at=at)
        )
