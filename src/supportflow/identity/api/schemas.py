"""identity 接口契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from supportflow.identity.domain.models import Principal


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class PrincipalOut(BaseModel):
    user_id: str
    email: str
    display_name: str
    role: str
    is_staff: bool

    @classmethod
    def of(cls, principal: Principal) -> PrincipalOut:
        return cls(
            user_id=str(principal.user_id),
            email=principal.email,
            display_name=principal.display_name,
            role=principal.role.value,
            is_staff=principal.is_staff,
        )
