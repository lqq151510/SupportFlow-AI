"""Alembic 运行环境。

两个刻意的决定：

1. 数据库地址来自 ``Settings``（``DATABASE_URL``），不写死在 ``alembic.ini`` ——
   应用与迁移共用同一事实来源，避免两处漂移。
2. ``target_metadata`` 取自 :func:`supportflow.bootstrap.schema.all_metadata`，
   它集中导入全部 ORM 表模块；漏掉任何一张表都会让 ``--autogenerate`` 生成
   删除该表语句，属于高风险错误，因此集中管理。
"""

from __future__ import annotations

from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import Connection, engine_from_config, pool

from supportflow.bootstrap.schema import all_metadata
from supportflow.shared.config import get_settings

config = context.config

if config.config_file_name is not None:
    # ``disable_existing_loggers`` 默认为 True，会把当前进程里已创建的日志器全部
    # 置为 disabled —— 而本项目会在**与应用共享配置的进程**里程序化执行迁移
    # （测试夹具、迁移容器），这等于静默关掉应用日志。
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# configparser 会把 % 当插值符，URL 里的百分号必须转义。
config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))

target_metadata = all_metadata()

_RUN_EVENT_PARTITION_PREFIX = "run_events_"


def _is_run_event_partition(name: str | None) -> bool:
    return bool(name) and name.startswith(_RUN_EVENT_PARTITION_PREFIX)


def include_object(
    obj: Any, name: str | None, type_: str, reflected: bool, compare_to: Any
) -> bool:
    """把 ``run_events`` 的月分区及其索引排除在比对之外。

    分区子表由 ``ensure_run_event_partitions`` 按需创建，**不存在于 ORM 元数据**。
    若不过滤，``alembic revision --autogenerate`` 会生成
    ``op.drop_table('run_events_202609')`` —— 一次自动生成就能静默删掉全部运行
    事件。这是本项目唯一必须显式屏蔽的结构差异。
    """
    if not reflected:
        return True
    if type_ == "table" and _is_run_event_partition(name):
        return False
    if type_ == "index":
        parent = getattr(getattr(obj, "table", None), "name", None)
        if _is_run_event_partition(parent) or _is_run_event_partition(name):
            return False
    return True


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL，不连库。"""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        _run_migrations(connection)


def _run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
