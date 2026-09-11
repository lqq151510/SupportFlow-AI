"""迁移与 schema 约束的集成测试。

这些断言的是**只在真实 PostgreSQL 上才存在**的性质：部分唯一索引、月分区、
外键级联方向。SQLite 上它们要么不存在，要么行为不同。
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from supportflow.shared.db import session_scope

REPO_ROOT = Path(__file__).resolve().parents[2]


def _scalar(sql: str) -> object:
    with session_scope() as session:
        return session.scalar(text(sql))


def test_migration_matches_orm_metadata(migrated: None) -> None:
    """``alembic check`` 无差异：手写迁移与 ORM 元数据完全一致。

    这是「迁移可在空库执行」之外的另一半保证 —— 否则下一次 autogenerate 会生成
    一堆莫名其妙的 ALTER。
    """
    from alembic import command
    from alembic.config import Config

    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    command.check(config)


def test_all_business_tables_exist(migrated: None) -> None:
    expected = {
        "users",
        "user_sessions",
        "tickets",
        "agent_runs",
        "run_events",
        "run_steps",
        "audit_logs",
        "idempotency_records",
    }
    with session_scope() as session:
        found = set(
            session.scalars(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
                )
            ).all()
        )
    # run_events 的月分区也会出现在 pg_tables 里，故用子集判断。
    assert expected <= found


def test_run_events_is_partitioned_by_created_at(migrated: None) -> None:
    partitioned = _scalar(
        "SELECT COUNT(*) FROM pg_partitioned_table p "
        "JOIN pg_class c ON c.oid = p.partrelid WHERE c.relname = 'run_events'"
    )
    assert partitioned == 1


def test_current_month_partition_exists_after_migration(migrated: None) -> None:
    """空库 upgrade head 之后必须立即可写，因此当月分区由迁移创建。"""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    expected = f"run_events_{now:%Y%m}"
    exists = _scalar(
        f"SELECT COUNT(*) FROM pg_class WHERE relname = '{expected}' AND relkind = 'r'"
    )
    assert exists == 1


def test_active_run_partial_unique_index_predicate(migrated: None) -> None:
    """部分唯一索引的谓词必须与 ACTIVE_RUN_STATUSES 严格一致。

    这是「同一工单同时只有一个活动运行」的唯一保证者 —— 应用层不做先查后写。
    """
    from supportflow.agent.domain.models import ACTIVE_RUN_STATUSES

    definition = _scalar(
        "SELECT indexdef FROM pg_indexes "
        "WHERE tablename = 'agent_runs' AND indexname = 'uq_agent_runs_active_per_ticket'"
    )
    assert isinstance(definition, str)
    assert "UNIQUE" in definition
    for status in ACTIVE_RUN_STATUSES:
        assert status.value in definition
    # 终态必须不在谓词里，否则同一工单的第二次运行会被错误拒绝。
    for terminal in ("COMPLETED", "NEEDS_HUMAN", "FAILED"):
        assert terminal not in definition


def test_tickets_reference_users_with_restrict_on_delete(migrated: None) -> None:
    rule = _scalar(
        "SELECT rc.delete_rule FROM information_schema.referential_constraints rc "
        "WHERE rc.constraint_name = 'fk_tickets_submitter_id_users'"
    )
    # 提交人不可被删除，避免工单失去归属。
    assert rule == "RESTRICT"


def test_audit_logs_have_no_foreign_key_on_actor(migrated: None) -> None:
    """审计只追加，且必须比用户活得久 —— 不允许外键级联删除。"""
    count = _scalar(
        "SELECT COUNT(*) FROM information_schema.table_constraints "
        "WHERE table_name = 'audit_logs' AND constraint_type = 'FOREIGN KEY'"
    )
    assert count == 0


def test_idempotency_scope_key_is_unique(migrated: None) -> None:
    count = _scalar(
        "SELECT COUNT(*) FROM information_schema.table_constraints "
        "WHERE table_name = 'idempotency_records' "
        "AND constraint_name = 'uq_idempotency_scope_key'"
    )
    assert count == 1


def test_empty_database_migration_is_repeatable(clean_db: None) -> None:
    """降级到 base 再升回 head：迁移脚本必须双向可用。"""
    from alembic import command
    from alembic.config import Config

    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "migrations"))

    def tickets_table_count() -> object:
        return _scalar(
            "SELECT COUNT(*) FROM pg_tables "
            "WHERE schemaname = 'public' AND tablename = 'tickets'"
        )

    command.downgrade(config, "base")
    assert tickets_table_count() == 0
    command.upgrade(config, "head")
    assert tickets_table_count() == 1
