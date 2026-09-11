"""种子与 Worker 入口的装配测试。

入口代码是最容易「看起来对、跑起来挂」的部分（依赖名拼错、环境变量没生效），
值得专门覆盖一次。
"""

from __future__ import annotations

import logging

import pytest

from supportflow.bootstrap import seed as seed_module
from supportflow.bootstrap import worker as worker_module
from supportflow.identity.domain.models import Role
from supportflow.shared.db import session_scope
from supportflow.shared.logging import configure_logging

DEMO_EMAILS = {email for email, _, _ in seed_module.DEMO_ACCOUNTS}


def _existing_roles() -> set[Role]:
    from sqlalchemy import select

    from supportflow.identity.infrastructure.tables import UserRow

    with session_scope() as session:
        return {
            Role(row.role)
            for row in session.scalars(
                select(UserRow).where(UserRow.email.in_(DEMO_EMAILS))
            ).all()
        }


def test_seed_is_idempotent_and_creates_all_roles(
    clean_db: None, caplog: pytest.LogCaptureFixture
) -> None:
    """首次执行建齐三个角色；重复执行跳过且不报错。"""
    configure_logging("INFO")
    with caplog.at_level(logging.INFO, logger=seed_module.__name__):
        seed_module.main()
        assert _existing_roles() == {Role.USER, Role.AGENT, Role.ADMIN}

        caplog.clear()
        seed_module.main()
        assert "跳过" in caplog.text
    assert _existing_roles() == {Role.USER, Role.AGENT, Role.ADMIN}


def test_seed_password_is_hashed_not_plaintext(clean_db: None) -> None:
    """演示口令只以 Argon2 哈希落库。"""
    from sqlalchemy import select

    from supportflow.identity.infrastructure.tables import UserRow

    seed_module.main()
    with session_scope() as session:
        hashes = session.scalars(
            select(UserRow.password_hash).where(UserRow.email.in_(DEMO_EMAILS))
        ).all()
    assert hashes
    assert all(h.startswith("$argon2") for h in hashes)


def test_worker_entrypoint_wires_everything_and_exits(
    clean_db: None, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """``main()`` 应完成装配（prepare_database + Worker 循环），且可通过中断退出。"""
    from supportflow.agent.application.worker import AgentWorker

    calls: list[str] = []

    def fake_run_forever(self: AgentWorker) -> None:
        calls.append("loop")
        raise KeyboardInterrupt

    monkeypatch.setattr(AgentWorker, "run_forever", fake_run_forever)
    with caplog.at_level(logging.INFO, logger=worker_module.__name__):
        worker_module.main()
        assert calls == ["loop"]
        assert "Worker 启动" in caplog.text
