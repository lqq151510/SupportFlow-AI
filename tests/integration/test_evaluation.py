"""冻结评测集与评测运行（真实 PostgreSQL）。

三条重点：

1. **导入幂等**：同一冻结集重复导入，`created + reused == 50`，不会产生重复用例；
2. **指标可计算**：Mock 模式下分类准确率与 Recall@5 都能算出来并落库；
3. **Mock ≠ 质量证据**（AGENTS.md §10）：断言的是"指标被如实计算与记录"，
   **不**断言达到 PLAN 的目标值 —— 目标是否达成要看真实模式的评测结果。
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import text

from supportflow.bootstrap.container import build_services
from supportflow.evaluation.frozen.loader import load_frozen_set
from supportflow.identity.domain.models import Principal, Role
from supportflow.identity.infrastructure.repository import SqlAlchemyUserRepository
from supportflow.shared.db import session_scope
from supportflow.shared.errors import Forbidden

API = "/api/v1"

EXPECTED_CASES = 50
EXPECTED_CORPUS = 12


def _admin() -> Principal:
    with session_scope() as session:
        row = SqlAlchemyUserRepository(session).find_by_email("admin@example.com")
    assert row is not None
    return Principal(
        user_id=row.id, email=row.email, display_name=row.display_name, role=Role(row.role)
    )


def _scalar(sql: str) -> object:
    with session_scope() as session:
        return session.execute(text(sql)).scalar()


@pytest.fixture
def admin() -> Principal:
    return _admin()


def test_frozen_set_has_the_planned_shape() -> None:
    """冻结集本身的结构契约：50 条 = 40 检索 + 10 安全，语料 12 篇。"""
    frozen = load_frozen_set()
    assert len(frozen.cases) == EXPECTED_CASES
    assert len(frozen.corpus) == EXPECTED_CORPUS

    keys = [case.case_key for case in frozen.cases]
    assert len(set(keys)) == EXPECTED_CASES, "case_key 必须唯一"

    retrieval = [case for case in frozen.cases if not case.expect_handoff]
    safety = [case for case in frozen.cases if case.expect_handoff]
    assert len(retrieval) == 40
    assert len(safety) == 10
    # 安全场景不考核分类（期望分类为空），但必须带期望来源或明确无来源。
    for case in safety:
        assert case.expected_ticket_category is None
    # 检索场景都必须带期望来源与期望分类，否则指标无从计算。
    for case in retrieval:
        assert case.expected_ticket_category is not None
        assert case.expected_source_ids, f"{case.case_key} 缺少期望来源"


def test_import_is_idempotent(
    client: object, demo_users: None, migrated: None, admin: Principal
) -> None:
    frozen = load_frozen_set()

    with session_scope() as session:
        services = build_services(session)
        first = services.evaluations.import_frozen(admin, frozen)
    assert first.created == EXPECTED_CASES
    assert first.total == EXPECTED_CASES

    with session_scope() as session:
        services = build_services(session)
        second = services.evaluations.import_frozen(admin, frozen)
    assert second.created == 0
    assert second.reused == EXPECTED_CASES
    assert second.total == EXPECTED_CASES

    # 语料已进知识库：12 篇冻结文档。
    with session_scope() as session:
        rows = session.execute(text("SELECT title FROM knowledge_documents")).all()
    titles = {str(row[0]) for row in rows}
    for doc in frozen.corpus:
        assert doc.title in titles


def test_only_admin_can_import_or_run(
    client: object, demo_users: None, migrated: None
) -> None:
    frozen = load_frozen_set()
    with session_scope() as session:
        row = SqlAlchemyUserRepository(session).find_by_email("customer@example.com")
    assert row is not None
    from supportflow.identity.domain.models import Role as R

    customer = Principal(
        user_id=row.id, email=row.email, display_name=row.display_name, role=R(row.role)
    )
    with session_scope() as session:
        services = build_services(session)
        with pytest.raises(Forbidden):
            services.evaluations.import_frozen(customer, frozen)
        with pytest.raises(Forbidden):
            services.evaluations.run_evaluation(customer, mode="mock")


def test_run_evaluation_computes_metrics_in_mock_mode(
    client: object, demo_users: None, migrated: None, admin: Principal
) -> None:
    frozen = load_frozen_set()
    with session_scope() as session:
        build_services(session).evaluations.import_frozen(admin, frozen)

    # 先取 20 条（字母序在前的是检索场景），断言分类与召回都有值。
    with session_scope() as session:
        run = build_services(session).evaluations.run_evaluation(admin, mode="mock", limit=20)

    assert run.status == "COMPLETED"
    assert run.metrics is not None
    metrics = run.metrics
    assert metrics["total_cases"] == 20
    assert metrics["category"]["total"] == 20
    assert metrics["recall_at_5"]["total"] == 20
    assert 0.0 <= metrics["category"]["accuracy"] <= 1.0
    assert 0.0 <= metrics["recall_at_5"]["rate"] <= 1.0

    # 指标带 PLAN 目标（≥90% / ≥80%），是否达成由真实模式评测判定。
    assert metrics["category"]["target"] == 0.9
    assert metrics["recall_at_5"]["target"] == 0.8


def test_results_are_persisted_per_case(
    client: object, demo_users: None, migrated: None, admin: Principal
) -> None:
    frozen = load_frozen_set()
    with session_scope() as session:
        services = build_services(session)
        services.evaluations.import_frozen(admin, frozen)
        run = services.evaluations.run_evaluation(admin, mode="mock", limit=5)

    with session_scope() as session:
        rows = session.execute(
            text(
                "SELECT category_correct, recall_at_5, detail_json "
                "FROM evaluation_results WHERE run_id = :r"
            ),
            {"r": run.id},
        ).all()

    assert len(rows) == 5
    for category_correct, recall, detail in rows:
        assert category_correct is not None
        assert recall is not None
        detail_dict = detail if isinstance(detail, dict) else json.loads(str(detail))
        assert "classified_category" in detail_dict


# --- HTTP 接口（导入 / 执行 / 报告导出） --------------------------------------


def test_evaluation_api_import_run_and_report(
    client: object, demo_users: None, migrated: None, login: object
) -> None:
    csrf = login("admin@example.com")

    imported = client.post(
        f"{API}/evaluations/import", headers={"X-CSRF-Token": csrf}
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["created"] == EXPECTED_CASES
    assert imported.json()["corpus_docs"] == EXPECTED_CORPUS

    created = client.post(
        f"{API}/evaluations/runs",
        json={"mode": "mock", "limit": 10},
        headers={"X-CSRF-Token": csrf},
    )
    assert created.status_code == 201, created.text
    run_id = created.json()["id"]
    assert created.json()["status"] == "COMPLETED"
    assert created.json()["metrics"]["total_cases"] == 10

    report = client.get(f"{API}/evaluations/runs/{run_id}/report")
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["metrics"]["total_cases"] == 10
    assert len(body["results"]) == 10
    # 报告必须可序列化为 JSON（导出契约）。
    json.dumps(body, ensure_ascii=False)


def test_evaluation_api_is_admin_only(
    client: object, demo_users: None, migrated: None, login: object
) -> None:
    customer_csrf = login("customer@example.com")
    forbidden = client.post(
        f"{API}/evaluations/runs",
        json={"mode": "mock"},
        headers={"X-CSRF-Token": customer_csrf},
    )
    assert forbidden.status_code == 403, forbidden.text

    agent_csrf = login("agent@example.com")
    forbidden_agent = client.post(
        f"{API}/evaluations/runs",
        json={"mode": "mock"},
        headers={"X-CSRF-Token": agent_csrf},
    )
    assert forbidden_agent.status_code == 403, forbidden_agent.text

    invalid_mode = client.post(
        f"{API}/evaluations/runs",
        json={"mode": "chatgpt"},
        headers={"X-CSRF-Token": login("admin@example.com")},
    )
    assert invalid_mode.status_code == 400, invalid_mode.text
