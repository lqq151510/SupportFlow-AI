"""LangGraph PostgreSQL checkpoint 适配。

迁移 ``0004_langgraph_checkpoints`` 已创建所需表，因此这里绝不调用
``PostgresSaver.setup()``。每次执行以运行 ID 作为 ``thread_id``，恢复同一运行时
必须传入同一配置，LangGraph 才会读取之前的检查点。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row


def checkpoint_dsn(database_url: str) -> str:
    """把 SQLAlchemy URL 转为 LangGraph/psycopg 使用的纯 psycopg DSN。"""
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def checkpoint_config(run_id: UUID) -> dict[str, dict[str, str]]:
    """固定 LangGraph 线程标识，禁止用工单 ID 混合不同运行的恢复记录。"""
    return {"configurable": {"thread_id": str(run_id)}}


@contextmanager
def postgres_checkpointer(database_url: str) -> Iterator[PostgresSaver]:
    """提供一次图调用使用的同步 checkpointer，连接关闭前完成检查点写入。"""
    with psycopg.connect(
        checkpoint_dsn(database_url),
        autocommit=True,
        row_factory=dict_row,
    ) as conn:
        yield PostgresSaver(conn)
