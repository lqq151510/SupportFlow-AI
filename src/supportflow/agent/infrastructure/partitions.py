"""``run_events`` 月分区维护。

分区表的 INSERT 只会路由到**已存在**的分区；若目标月份没有分区且没有 DEFAULT
分区，插入会直接失败。因此在 API 与 Worker 启动时都会调用
:func:`ensure_run_event_partitions` 预建当月及未来若干月的分区。

保留策略（PLAN.md 已锁定：在线保留 30 天）通过 ``DROP TABLE <分区>`` 实现，
而不是 ``DELETE`` —— 运行事件表是只追加的，不提供物理删除接口。
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

PARTITION_PREFIX = "run_events"


def partition_name(year: int, month: int) -> str:
    return f"{PARTITION_PREFIX}_{year:04d}{month:02d}"


def _shift(year: int, month: int, offset: int) -> tuple[int, int]:
    index = (year * 12 + (month - 1)) + offset
    return index // 12, index % 12 + 1


def month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    next_year, next_month = _shift(year, month, 1)
    return start, date(next_year, next_month, 1)


def ensure_run_event_partitions(
    session: Session, *, horizon_months: int = 2, today: date | None = None
) -> list[str]:
    """创建缺失的月份分区，返回本次新建的分区名。已存在时为空列表。"""
    base = today or date.today()
    created: list[str] = []
    for offset in range(horizon_months + 1):
        year, month = _shift(base.year, base.month, offset)
        name = partition_name(year, month)
        exists = session.scalar(
            text("SELECT to_regclass(:qualified)"), {"qualified": f"public.{name}"}
        )
        if exists is not None:
            continue
        start, end = month_bounds(year, month)
        session.execute(
            text(
                f"CREATE TABLE IF NOT EXISTS {name} PARTITION OF {PARTITION_PREFIX} "
                f"FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}')"
            )
        )
        created.append(name)
    return created


def list_partitions(session: Session) -> list[str]:
    """列出 ``run_events`` 当前已存在的分区名，按名称升序。"""
    rows = session.execute(
        text(
            "SELECT child.relname "
            "FROM pg_inherits i "
            "JOIN pg_class child ON child.oid = i.inhrelid "
            "JOIN pg_class parent ON parent.oid = i.inhparent "
            "WHERE parent.relname = :parent "
            "ORDER BY child.relname"
        ),
        {"parent": PARTITION_PREFIX},
    ).scalars()
    return list(rows)
