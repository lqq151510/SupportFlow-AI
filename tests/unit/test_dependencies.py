"""角色依赖的行为单测。

``require_staff`` / ``require_admin`` 目前没有路由直接使用（角色判定当前由应用服务
承担），但它们是 identity 接口层的公开契约，必须被验证而不是留着当装饰。
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from supportflow.identity.api.dependencies import require_admin, require_staff
from supportflow.identity.domain.models import Principal, Role
from supportflow.shared.errors import Forbidden


def _principal(role: Role) -> Principal:
    return Principal(
        user_id=uuid4(),
        email=f"{role.value.lower()}@example.com",
        display_name=role.value,
        role=role,
    )


@pytest.mark.parametrize("role", [Role.AGENT, Role.ADMIN])
def test_require_staff_accepts_staff_roles(role: Role) -> None:
    assert require_staff(_principal(role)).role is role


def test_require_staff_rejects_regular_user() -> None:
    with pytest.raises(Forbidden) as excinfo:
        require_staff(_principal(Role.USER))
    assert excinfo.value.code == "forbidden"


def test_require_admin_accepts_admin_only() -> None:
    assert require_admin(_principal(Role.ADMIN)).role is Role.ADMIN
    for role in (Role.USER, Role.AGENT):
        with pytest.raises(Forbidden):
            require_admin(_principal(role))


def test_principal_derives_staff_and_admin_flags() -> None:
    agent = _principal(Role.AGENT)
    admin = _principal(Role.ADMIN)
    user = _principal(Role.USER)
    assert agent.is_staff and not agent.is_admin
    assert admin.is_staff and admin.is_admin
    assert not user.is_staff and not user.is_admin
