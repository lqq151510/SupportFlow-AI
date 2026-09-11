"""演示账号种子。

幂等：按邮箱查一次，已存在则跳过，因此可以随容器启动反复执行。

口令来自 ``SEED_DEMO_PASSWORD``（默认 ``demo1234``）——**只用于本地演示**，
且只以 Argon2 哈希落库。生产环境不应执行本模块。

用法::

    python -m supportflow.bootstrap.seed
"""

from __future__ import annotations

import logging
import os

from supportflow.identity.domain.models import NewUser, Role
from supportflow.identity.infrastructure.repository import SqlAlchemyUserRepository
from supportflow.identity.infrastructure.security import Argon2PasswordHasher
from supportflow.shared.config import get_settings
from supportflow.shared.db import session_scope
from supportflow.shared.logging import configure_logging

logger = logging.getLogger(__name__)

DEFAULT_PASSWORD = "demo1234"

#: (邮箱, 显示名, 角色) —— 三个角色各一个，覆盖本阶段的可见性差异。
DEMO_ACCOUNTS: tuple[tuple[str, str, Role], ...] = (
    ("customer@example.com", "演示客户", Role.USER),
    ("agent@example.com", "演示坐席", Role.AGENT),
    ("admin@example.com", "演示管理员", Role.ADMIN),
)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    password = os.environ.get("SEED_DEMO_PASSWORD", DEFAULT_PASSWORD)
    hasher = Argon2PasswordHasher()

    created: list[str] = []
    with session_scope() as session:
        users = SqlAlchemyUserRepository(session)
        for email, display_name, role in DEMO_ACCOUNTS:
            if users.find_by_email(email) is not None:
                continue
            users.add(
                NewUser(
                    email=email,
                    display_name=display_name,
                    role=role,
                    password_hash=hasher.hash(password),
                )
            )
            created.append(email)

    if created:
        logger.info("已创建演示账号: %s", ", ".join(created))
    else:
        logger.info("演示账号已存在，跳过")


if __name__ == "__main__":  # pragma: no cover
    main()
