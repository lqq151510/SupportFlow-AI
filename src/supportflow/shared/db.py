"""数据库引擎与会话。

业务事务统一使用**同步** SQLAlchemy ``Session``（psycopg 3）。FastAPI 的同步路由函数
会被放入线程池执行，因此阻塞式数据库调用不会占用事件循环 —— 见 AGENTS.md §5。

禁止在 ``async def`` 中直接使用这里的 ``Session``。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from supportflow.shared.config import get_settings


class Base(DeclarativeBase):
    """全部 ORM 表的声明基类。"""


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_pre_ping=True,
        future=True,
    )


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    """请求级事务边界：正常退出提交，异常回滚。"""
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine_cache() -> None:
    """测试用：丢弃缓存的引擎与会话工厂。"""
    get_sessionmaker.cache_clear()
    get_engine.cache_clear()
