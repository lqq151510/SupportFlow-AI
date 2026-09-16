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
        "import_jobs",
        "knowledge_documents",
        "knowledge_chunks",
        "history_tickets",
        "checkpoint_migrations",
        "checkpoints",
        "checkpoint_blobs",
        "checkpoint_writes",
        "model_configs",
        "knowledge_chunk_vectors",
        "history_ticket_vectors",
        "action_requests",
        "action_ledger",
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


def test_knowledge_indexes_use_vector_and_gin(migrated: None) -> None:
    extension = _scalar("SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'")
    assert extension == 1
    with session_scope() as session:
        definitions = dict(
            session.execute(
                text(
                    "SELECT indexname, indexdef FROM pg_indexes "
                    "WHERE indexname IN ("
                    "'ix_knowledge_chunks_tsv', "
                    "'ix_knowledge_chunks_embedding_hnsw', "
                    "'ix_history_tickets_tsv', "
                    "'ix_history_tickets_embedding_hnsw'"
                    ")"
                )
            ).all()
        )
    assert "USING gin" in definitions["ix_knowledge_chunks_tsv"]
    assert "USING hnsw" in definitions["ix_knowledge_chunks_embedding_hnsw"]
    assert "USING gin" in definitions["ix_history_tickets_tsv"]
    assert "USING hnsw" in definitions["ix_history_tickets_embedding_hnsw"]


def test_action_ledger_pairs_of_unique_constraints_are_idempotency_boundaries(
    migrated: None,
) -> None:
    """PLAN 表 #16 明确：「两个唯一约束即幂等边界」。

    账本的幂等不靠应用层判重，而靠 ``action_request_id`` 与 ``idempotency_key``
    两个唯一约束。少了任何一个，重复审批或检查点重放就会产生第二笔业务效果。
    """
    unique_columns = _scalar(
        "SELECT string_agg(DISTINCT a.attname, ',' ORDER BY a.attname) "
        "FROM pg_index i "
        "JOIN pg_class c ON c.oid = i.indrelid "
        "JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(i.indkey) "
        "WHERE c.relname = 'action_ledger' AND i.indisunique "
        "AND i.indnatts = 1 AND a.attname IN ('action_request_id', 'idempotency_key')"
    )
    assert unique_columns == "action_request_id,idempotency_key", unique_columns


def test_action_requests_allow_only_one_pending_per_run_and_action(migrated: None) -> None:
    """同一运行 + 同一动作类型至多一个待审批申请。

    部分唯一索引的谓词必须是 ``status = 'PENDING'``：已处理的申请不该继续占位，
    否则「先被拒绝、再重新申请」会被数据库挡掉。
    """
    definition = _scalar(
        "SELECT indexdef FROM pg_indexes WHERE tablename = 'action_requests' "
        "AND indexname = 'uq_action_requests_pending_per_run'"
    )
    assert isinstance(definition, str)
    assert "UNIQUE" in definition
    assert "run_id" in definition and "action_type" in definition
    # Postgres 会把谓词规范化成 ((status)::text = 'PENDING')，因此只断言两个要素存在。
    assert "status" in definition and "PENDING" in definition


def test_action_requests_has_expiry_scan_index(migrated: None) -> None:
    """AGENTS.md §7 要求为审批到期扫描建立可解释索引。"""
    definition = _scalar(
        "SELECT indexdef FROM pg_indexes WHERE tablename = 'action_requests' "
        "AND indexname = 'ix_action_requests_status_expires'"
    )
    assert isinstance(definition, str)
    assert "status" in definition and "expires_at" in definition


def test_versioned_vector_tables_are_dimension_bound(migrated: None) -> None:
    """新版向量表的列维度必须是 1024，且带 HNSW 索引。

    维度是索引版本契约的一部分：该表只服务一个索引版本，因此列维度写死在迁移里。
    若有人把它改成别的维度，跨索引版本混用向量就会变成可能。
    """
    for table, pk_columns in (
        ("knowledge_chunk_vectors", ("chunk_id", "index_version")),
        ("history_ticket_vectors", ("ticket_id", "index_version")),
    ):
        column_type = _scalar(
            "SELECT format_type(a.atttypid, a.atttypmod) FROM pg_attribute a "
            "JOIN pg_class c ON c.oid = a.attrelid "
            f"WHERE c.relname = '{table}' AND a.attname = 'embedding'"
        )
        assert column_type == "vector(1024)", column_type

        primary_key = _scalar(
            "SELECT string_agg(a.attname, ',' ORDER BY array_position(i.indkey, a.attnum)) "
            "FROM pg_index i "
            "JOIN pg_class c ON c.oid = i.indrelid "
            "JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(i.indkey) "
            f"WHERE c.relname = '{table}' AND i.indisprimary"
        )
        assert primary_key == ",".join(pk_columns), primary_key

        index_def = _scalar(
            "SELECT indexdef FROM pg_indexes WHERE tablename = "
            f"'{table}' AND indexname LIKE '%embedding_hnsw'"
        )
        assert isinstance(index_def, str)
        assert "hnsw" in index_def and "vector_cosine_ops" in index_def


def test_model_configs_enabled_is_unique_per_capability(migrated: None) -> None:
    """每类能力至多一个启用配置。

    这是「单工作区每类能力只启用一个」的**唯一保证者** —— 应用层不做先查后写判重，
    启用新配置必须在一个事务里先停用旧的。
    """
    definition = _scalar(
        "SELECT indexdef FROM pg_indexes WHERE tablename = 'model_configs' "
        "AND indexname = 'uq_model_configs_enabled_per_capability'"
    )
    assert isinstance(definition, str)
    assert "UNIQUE" in definition
    assert "capability" in definition
    # 谓词必须限定 enabled，否则「每个能力只能有一条记录」会被误当成约束。
    assert "WHERE enabled" in definition


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
