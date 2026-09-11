"""运行配置。

所有可调项集中在此，环境变量优先于默认值。字段名即环境变量名（大小写不敏感），
例如 ``database_url`` 对应 ``DATABASE_URL``。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ModelMode = Literal["mock", "real"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # 允许 model_mode / model_secret_master_key 这类以 model_ 开头的字段名。
        protected_namespaces=(),
    )

    app_name: str = "SupportFlow Agent"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://supportflow:supportflow@localhost:5432/supportflow"
    database_echo: bool = False

    # 模型接入。mock 为确定性离线实现，real 走外部 OpenAI-compatible API。
    # 禁止在运行中切换，也不允许真实模式失败时降级为 mock。
    model_mode: ModelMode = "mock"
    model_secret_master_key: str = ""
    chat_model_name: str = "mock-chat"
    model_request_timeout_seconds: float = 30.0
    model_max_attempts: int = 3
    run_max_tool_calls: int = 8

    upload_dir: Path = Path("var/uploads")

    session_cookie_name: str = "sf_session"
    session_ttl_seconds: int = 24 * 3600
    csrf_cookie_name: str = "sf_csrf"
    csrf_header_name: str = "X-CSRF-Token"
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    worker_poll_interval_seconds: float = 1.0
    worker_lease_owner: str = "worker-local"
    run_lease_seconds: int = 60

    # SSE 事件流。轮询间隔决定事件可见延迟；上限时长到达后主动收流，避免连接
    # 无限期占用线程；心跳注释帧用于穿透中间代理的空闲超时。
    sse_poll_interval_seconds: float = 0.5
    sse_max_duration_seconds: float = 300.0
    sse_heartbeat_polls: int = 20
    #: 前端 ``EventSource`` 的重连退避（毫秒），随流首帧下发。
    sse_retry_ms: int = 3000

    request_id_header: str = "X-Request-Id"


@lru_cache
def get_settings() -> Settings:
    """进程内单例。测试中可通过 ``get_settings.cache_clear()`` 重置。"""
    return Settings()
