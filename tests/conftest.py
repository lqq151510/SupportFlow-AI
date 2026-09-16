"""测试夹具。

集成测试需要**真实 PostgreSQL**：本项目的核心不变量（部分唯一索引互斥、租约、
``FOR UPDATE SKIP LOCKED``、月分区、JSONB 幂等表）都只在真实数据库上才成立，
用 SQLite 或 mock 验证等于没验证。

数据库来源按优先级：

1. ``TEST_DATABASE_URL`` 环境变量（CI 里复用已起的服务，最快）；
2. 否则用 Testcontainers 起一个 ``pgvector/pgvector:pg17`` 容器。

会话级夹具负责把 ``DATABASE_URL`` 指向测试库、清空配置缓存，并把 schema 迁到
``head``；每个用例前 TRUNCATE 全部业务表，保证用例之间互不干扰。
"""

from __future__ import annotations

import base64
import os
from collections.abc import Callable, Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from supportflow.bootstrap.api import create_app
from supportflow.bootstrap.seed import DEFAULT_PASSWORD
from supportflow.bootstrap.seed import main as seed_main
from supportflow.identity.domain.models import NewUser, Role
from supportflow.identity.infrastructure.repository import SqlAlchemyUserRepository
from supportflow.identity.infrastructure.security import Argon2PasswordHasher
from supportflow.shared.config import get_settings
from supportflow.shared.db import reset_engine_cache, session_scope

REPO_ROOT = Path(__file__).resolve().parents[1]
API = "/api/v1"
PG_IMAGE = "pgvector/pgvector:pg17"

#: 测试专用主密钥：base64 编码的 32 字节，仅用于验证加解密行为。
#: **不是任何真实环境的密钥**，真实主密钥只允许来自部署环境变量。
TEST_MASTER_KEY = base64.b64encode(b"supportflow-test-master-key-32b!").decode("ascii")


def parse_sse(body: str) -> list[tuple[int | None, str, dict[str, object]]]:
    """把 SSE 文本还原成 ``(id, event, data)`` 列表。

    ``id`` 为 ``None`` 的帧由服务端即时生成（例如 ``stream.closed``），不对应持久化事件。
    """
    import json as _json

    frames: list[tuple[int | None, str, dict[str, object]]] = []
    for block in body.split("\n\n"):
        if not block.strip() or block.startswith(":"):
            continue
        event_id: int | None = None
        event_name = ""
        data: dict[str, object] = {}
        for line in block.split("\n"):
            if line.startswith("id: "):
                event_id = int(line[4:])
            elif line.startswith("event: "):
                event_name = line[7:]
            elif line.startswith("data: "):
                data = _json.loads(line[6:])
        if event_name:
            frames.append((event_id, event_name, data))
    return frames

#: 按外键依赖倒序排列，TRUNCATE ... CASCADE 一次性清空。
BUSINESS_TABLES = (
    "evaluation_results",
    "evaluation_runs",
    "evaluation_cases",
    "action_ledger",
    "action_requests",
    "history_ticket_vectors",
    "knowledge_chunk_vectors",
    "history_tickets",
    "knowledge_chunks",
    "knowledge_documents",
    "import_jobs",
    "model_configs",
    "idempotency_records",
    "audit_logs",
    "run_steps",
    "run_events",
    "agent_runs",
    "tickets",
    "user_sessions",
    "users",
)


def _containers_url() -> Iterator[str]:
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer(PG_IMAGE, driver="psycopg") as container:
        yield container.get_connection_url()


def _reset_caches() -> None:
    get_settings.cache_clear()
    reset_engine_cache()


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    override = os.environ.get("TEST_DATABASE_URL")
    if override:
        yield override
        return
    yield from _containers_url()


@pytest.fixture(scope="session")
def configured_env(database_url: str) -> Iterator[None]:
    """把进程环境指向测试库，并让配置/引擎缓存失效。

    ``get_settings`` 与 ``get_engine`` 都是 ``lru_cache`` 单例，缓存不清就等于用
    默认的 localhost:5432 跑测试 —— 会静默连到开发库上。
    """
    previous = {
        key: os.environ.get(key)
        for key in (
            "DATABASE_URL",
            "MODEL_MODE",
            "SEED_DEMO_PASSWORD",
            "MODEL_SECRET_MASTER_KEY",
        )
    }
    os.environ["DATABASE_URL"] = database_url
    os.environ["MODEL_MODE"] = "mock"
    # 加密路径需要主密钥；用测试专用值，避免真实密钥进入测试进程。
    os.environ["MODEL_SECRET_MASTER_KEY"] = TEST_MASTER_KEY
    _reset_caches()
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        _reset_caches()


@pytest.fixture(scope="session")
def migrated(configured_env: None) -> None:
    """把测试库迁到 head。空库执行是本项目的硬性要求之一。"""
    from alembic import command
    from alembic.config import Config

    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    command.upgrade(config, "head")


def _truncate() -> None:
    with session_scope() as session:
        session.execute(text(f"TRUNCATE {', '.join(BUSINESS_TABLES)} CASCADE"))


@pytest.fixture
def clean_db(migrated: None) -> None:
    _truncate()


@pytest.fixture
def client(clean_db: None) -> Iterator[TestClient]:
    # with 语句会触发 lifespan，即 prepare_database() 预建运行事件分区。
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def demo_users(clean_db: None) -> None:
    seed_main()


@pytest.fixture
def create_user(clean_db: None) -> Callable[..., str]:
    """直接建账号，用于构造「另一个用户」这类种子数据覆盖不到的场景。"""
    hasher = Argon2PasswordHasher()

    def _create(email: str, role: Role = Role.USER, password: str = DEFAULT_PASSWORD) -> str:
        with session_scope() as session:
            SqlAlchemyUserRepository(session).add(
                NewUser(
                    email=email,
                    display_name=email.split("@")[0],
                    role=role,
                    password_hash=hasher.hash(password),
                )
            )
        return password

    return _create


@pytest.fixture
def login(client: TestClient) -> Callable[..., str]:
    """登录并返回 CSRF 令牌（前端要从可读 Cookie 里取出再回填请求头）。"""

    def _login(email: str, password: str = DEFAULT_PASSWORD) -> str:
        response = client.post(f"{API}/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200, response.text
        csrf = client.cookies.get(get_settings().csrf_cookie_name)
        assert csrf, "登录响应未下发 CSRF Cookie"
        return csrf

    return _login


@pytest.fixture
def logged_in_customer(demo_users: None, login: Callable[..., str]) -> str:
    return login("customer@example.com")


@pytest.fixture
def logged_in_agent(demo_users: None, login: Callable[..., str]) -> str:
    return login("agent@example.com")


@pytest.fixture
def logged_in_admin(demo_users: None, login: Callable[..., str]) -> str:
    return login("admin@example.com")


@pytest.fixture
def indexed_knowledge(
    client: TestClient, demo_users: None, login: Callable[..., str]
) -> None:
    """导入一条知识，让 Agent 运行能检索到证据并产出可交付草稿。

    状态图遵守 PLAN.md §3：检索为空时转人工，因此需要「完成」结果的用例必须先建索引。
    导入使用管理员会话；调用方应把 ``logged_in_customer`` 排在本夹具之后，
    以便后续请求回到客户身份。
    """
    admin_csrf = login("admin@example.com")
    response = client.post(
        f"{API}/knowledge/imports",
        files={
            "file": (
                "delivery.md",
                "# 物流延误处理\n物流长时间未更新时，核实后补发并告知客户新的时效。".encode(),
                "text/markdown",
            )
        },
        headers={
            "X-CSRF-Token": admin_csrf,
            "Idempotency-Key": f"seed-knowledge-{uuid4().hex}",
        },
    )
    assert response.status_code == 202, response.text
