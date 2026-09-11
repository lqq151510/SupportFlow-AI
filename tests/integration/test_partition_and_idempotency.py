"""``run_events`` 月分区维护与幂等存储的行为测试。

分区维护策略：在线保留 30 天（PLAN.md），到期用 ``DROP TABLE`` 而不是 ``DELETE``
—— 事件表只追加，不提供物理删除接口。这里验证「按需补建 + 幂等」与查询辅助。
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from supportflow.agent.infrastructure.partitions import (
    ensure_run_event_partitions,
    list_partitions,
    month_bounds,
    partition_name,
)
from supportflow.shared.db import session_scope
from supportflow.shared.errors import IdempotencyKeyReused
from supportflow.shared.idempotency import (
    IdempotencyKeyInProgress,
    IdempotencyStore,
    fingerprint,
)

# --- 月分区维护 -------------------------------------------------------------


def test_month_bounds_are_half_open() -> None:
    start, end = month_bounds(2026, 9)
    assert (start.isoformat(), end.isoformat()) == ("2026-09-01", "2026-10-01")
    # 12 月要正确翻年。
    assert month_bounds(2026, 12)[1].isoformat() == "2027-01-01"
    # 闰年 2 月只到 3 月 1 日。
    assert month_bounds(2028, 2)[1].isoformat() == "2028-03-01"


def test_partition_naming_is_zero_padded() -> None:
    assert partition_name(2026, 9) == "run_events_202609"
    assert partition_name(2027, 1) == "run_events_202701"


def test_ensure_partitions_creates_missing_months_and_is_idempotent(
    clean_db: None,
) -> None:
    """迁移只建了当月与未来两个月；拉长视界应补齐更远的月份，重复执行无动作。"""
    with session_scope() as session:
        created = ensure_run_event_partitions(session, horizon_months=5)
        # 迁移已建当月起 3 个月；视界 horizon+1 = 6 个月，应再补 3 个月。
        assert len(created) == 3

        before = list_partitions(session)
        again = ensure_run_event_partitions(session, horizon_months=5)
        after = list_partitions(session)
        assert again == []
        assert after == before
        assert len(after) == 6


def test_insert_outside_existing_partition_fails_loudly(clean_db: None) -> None:
    """分区缺失必须报错而不是静默吞数据 —— 这是维护任务存在的原因。"""
    with session_scope() as session, pytest.raises(IntegrityError):
        session.execute(
            text(
                "INSERT INTO run_events (id, created_at, run_id, event_type, payload) "
                "VALUES (nextval('run_events_id_seq'), '2030-01-15T00:00:00Z', "
                "'00000000-0000-4000-8000-000000000000', 'run.started', '{}')"
            )
        )


def test_list_partitions_returns_ascending_names(clean_db: None) -> None:
    with session_scope() as session:
        names = list_partitions(session)
    assert names == sorted(names)
    assert all(name.startswith("run_events_") for name in names)


# --- 幂等存储 ---------------------------------------------------------------


def test_reserve_twice_while_in_progress_raises_conflict(clean_db: None) -> None:
    """相同幂等键的并发请求必须 409，而不是各自执行一遍。"""
    with session_scope() as session:
        store = IdempotencyStore(session)
        request_hash = fingerprint({"body": "x"})
        assert store.reserve("scope-a", "key-000000001", request_hash) is None
        with pytest.raises(IdempotencyKeyInProgress):
            store.reserve("scope-a", "key-000000001", request_hash)


def test_completed_key_replays_original_response(clean_db: None) -> None:
    with session_scope() as session:
        store = IdempotencyStore(session)
        request_hash = fingerprint({"body": "x"})
        assert store.reserve("scope-a", "key-000000002", request_hash) is None
        store.complete(
            "scope-a", "key-000000002", status_code=202, body={"ticket_id": "t1"}
        )

    with session_scope() as session:
        replayed = IdempotencyStore(session).reserve(
            "scope-a", "key-000000002", fingerprint({"body": "x"})
        )
    assert replayed is not None
    assert replayed.status_code == 202
    assert replayed.body == {"ticket_id": "t1"}


def test_same_key_with_different_payload_is_rejected(clean_db: None) -> None:
    with session_scope() as session:
        store = IdempotencyStore(session)
        assert store.reserve("scope-a", "key-000000003", fingerprint({"v": 1})) is None
        store.complete("scope-a", "key-000000003", status_code=200, body={})

    with session_scope() as session, pytest.raises(IdempotencyKeyReused):
        IdempotencyStore(session).reserve(
            "scope-a", "key-000000003", fingerprint({"v": 2})
        )


def test_expired_record_is_recycled_not_replayed(clean_db: None) -> None:
    """过期记录被原行复用：唯一约束不允许插新行，语义上视为一次全新请求。"""
    with session_scope() as session:
        store = IdempotencyStore(session, ttl_seconds=0)
        assert store.reserve("scope-a", "key-000000004", fingerprint({"v": 1})) is None
        store.complete("scope-a", "key-000000004", status_code=202, body={"old": True})

    with session_scope() as session:
        store = IdempotencyStore(session, ttl_seconds=3600)
        # 新内容、同键：因已过期，应作为首次执行处理，而不是 409。
        assert store.reserve("scope-a", "key-000000004", fingerprint({"v": 2})) is None


def test_same_key_in_different_scopes_is_independent(clean_db: None) -> None:
    """作用域隔离：工单创建与草稿发布可以共用同一个客户端生成的键。"""
    with session_scope() as session:
        store = IdempotencyStore(session)
        request_hash = fingerprint({"v": 1})
        assert store.reserve("tickets", "shared-key-00001", request_hash) is None
        assert store.reserve("drafts", "shared-key-00001", request_hash) is None


def test_failed_request_does_not_burn_the_key(clean_db: None) -> None:
    """占位发生在事务里：请求失败回滚后，同一键应可重试（这里是回滚的等价模拟）。"""
    request_hash = fingerprint({"v": 1})
    with session_scope() as session:
        store = IdempotencyStore(session)
        assert store.reserve("scope-a", "key-000000005", request_hash) is None
        # 不调用 complete，直接让事务回滚（session_scope 异常路径的等价行为）。
        session.rollback()

    with session_scope() as session:
        assert IdempotencyStore(session).reserve("scope-a", "key-000000005", request_hash) is None
