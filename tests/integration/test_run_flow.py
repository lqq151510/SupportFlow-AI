"""运行执行、租约互斥与 SSE 事件流的集成测试。

事件契约是**对外接口**（前端按 ``event:`` 分发），因此这里断言具体事件名，
而不是「有事件就行」。

阶段 3 起运行由 LangGraph 状态图驱动，节点固定为
``load_ticket → classify_clean → retrieve_knowledge → tool_decision →
generate_draft → validate_citations → persist_result → propose_action``，共 8 个步骤。
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from supportflow.agent.application.executor import LEASE_LOST
from supportflow.agent.application.worker import AgentWorker
from supportflow.agent.domain.models import RunStatus
from supportflow.agent.infrastructure.repository import SqlAlchemyRunRepository
from supportflow.bootstrap.container import build_execution_unit, execution_unit_scope
from supportflow.identity.domain.models import Role
from supportflow.model.infrastructure.mock_gateway import MockChatGateway
from supportflow.shared.db import session_scope
from tests.conftest import API, parse_sse

SUBJECT = "快递一直没到"
BODY = "订单 A-2026-0901 的快递三天没有更新了，请帮我查一下物流"

#: 状态图的正常路径步骤数。检索为空时会提前转人工，步数因此更少。
HAPPY_PATH_STEPS = 8


def _submit(client: TestClient, csrf: str, key: str) -> dict[str, str]:
    response = client.post(
        f"{API}/tickets",
        json={"subject": SUBJECT, "body": BODY},
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": key},
    )
    assert response.status_code == 202, response.text
    return response.json()


def _run_worker_once(owner: str = "test-worker") -> bool:
    worker = AgentWorker(
        open_unit=execution_unit_scope,
        owner=owner,
        lease_seconds=30,
        poll_interval_seconds=0.0,
    )
    return worker.run_once()


# --- Worker 执行 ------------------------------------------------------------


def test_worker_completes_queued_run_and_classifies_ticket(
    client: TestClient,
    demo_users: None,
    indexed_knowledge: None,
    logged_in_customer: str,
) -> None:
    submitted = _submit(client, logged_in_customer, "worker-key-0001")
    assert _run_worker_once() is True

    run = client.get(f"{API}/runs/{submitted['run_id']}").json()
    assert run["status"] == RunStatus.COMPLETED.value
    assert run["step_count"] == HAPPY_PATH_STEPS
    assert run["chat_model_name"] == "mock-chat-v1"
    assert run["error_code"] is None

    ticket = client.get(f"{API}/tickets/{submitted['ticket_id']}").json()
    assert ticket["category"] == "DELIVERY"
    assert ticket["category_label"] == "配送物流"
    # 工单状态不因分类而改变：关闭仍需人工。
    assert ticket["status"] == "OPEN"


def test_run_without_any_evidence_goes_to_human(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    """知识库为空时检索不到证据，状态图必须转人工而不是生成无证据结论。"""
    submitted = _submit(client, logged_in_customer, "no-evidence-key-1")
    assert _run_worker_once() is True

    run = client.get(f"{API}/runs/{submitted['run_id']}").json()
    assert run["status"] == RunStatus.NEEDS_HUMAN.value
    assert run["error_code"] == "retrieval_empty"
    assert client.get(f"{API}/tickets/{submitted['ticket_id']}").json()["category"] is None


def test_worker_returns_false_when_no_run_is_queued(
    client: TestClient, demo_users: None
) -> None:
    assert _run_worker_once() is False


def test_worker_lease_is_not_required_twice_for_same_run(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    _submit(client, logged_in_customer, "worker-key-0002")
    assert _run_worker_once() is True
    # 已完成的运行不会被再次领取。
    assert _run_worker_once() is False


# --- 租约互斥 ---------------------------------------------------------------


def test_second_run_while_first_is_active_is_rejected(
    client: TestClient,
    demo_users: None,
    logged_in_customer: str,
    login: Callable[..., str],
) -> None:
    """工单已有 QUEUED 运行时，人工再发起一次必须 409（部分唯一索引兜底）。"""
    submitted = _submit(client, logged_in_customer, "active-run-key-1")
    client.post(f"{API}/auth/logout", headers={"X-CSRF-Token": logged_in_customer})
    staff_csrf = login("agent@example.com")

    response = client.post(
        f"{API}/tickets/{submitted['ticket_id']}/runs",
        json={},
        headers={"X-CSRF-Token": staff_csrf, "Idempotency-Key": "manual-run-key-01"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "run_already_active"


def test_manual_retry_after_completion_creates_linked_run(
    client: TestClient,
    demo_users: None,
    indexed_knowledge: None,
    logged_in_customer: str,
    login: Callable[..., str],
) -> None:
    submitted = _submit(client, logged_in_customer, "retry-key-0001")
    assert _run_worker_once() is True

    client.post(f"{API}/auth/logout", headers={"X-CSRF-Token": logged_in_customer})
    staff_csrf = login("agent@example.com")
    response = client.post(
        f"{API}/tickets/{submitted['ticket_id']}/runs",
        json={},
        headers={"X-CSRF-Token": staff_csrf, "Idempotency-Key": "retry-run-key-001"},
    )
    assert response.status_code == 202, response.text
    new_run = response.json()
    assert new_run["id"] != submitted["run_id"]
    # 关联原记录，而不是原地复活旧运行。
    assert new_run["retry_of_run_id"] == submitted["run_id"]
    assert new_run["status"] == "QUEUED"

    runs = client.get(f"{API}/tickets/{submitted['ticket_id']}/runs").json()["items"]
    assert [run["status"] for run in runs] == ["COMPLETED", "QUEUED"]


def test_manual_retry_replay_returns_same_run(
    client: TestClient,
    demo_users: None,
    logged_in_customer: str,
    login: Callable[..., str],
) -> None:
    submitted = _submit(client, logged_in_customer, "retry-key-0002")
    assert _run_worker_once() is True
    client.post(f"{API}/auth/logout", headers={"X-CSRF-Token": logged_in_customer})
    staff_csrf = login("agent@example.com")

    headers = {"X-CSRF-Token": staff_csrf, "Idempotency-Key": "retry-run-key-002"}
    first = client.post(f"{API}/tickets/{submitted['ticket_id']}/runs", json={}, headers=headers)
    second = client.post(f"{API}/tickets/{submitted['ticket_id']}/runs", json={}, headers=headers)
    assert first.json()["id"] == second.json()["id"]


def test_manual_retry_requires_staff(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    submitted = _submit(client, logged_in_customer, "retry-key-0003")
    response = client.post(
        f"{API}/tickets/{submitted['ticket_id']}/runs",
        json={},
        headers={"X-CSRF-Token": logged_in_customer, "Idempotency-Key": "retry-run-key-003"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_executor_abandons_writeback_when_lease_is_lost(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    """租约被接管后必须放弃写回 —— 这是「至多一次业务效果」的最后一道闸。"""
    submitted = _submit(client, logged_in_customer, "lease-key-0001")
    run_id = UUID(submitted["run_id"])

    with session_scope() as session:
        runs = SqlAlchemyRunRepository(session)
        claimed = runs.claim(run_id, owner="worker-a", lease_seconds=60)
        assert claimed is not None

        unit = build_execution_unit(session, gateway=MockChatGateway())
        outcome = unit.executor.execute(claimed, owner="worker-b")

    assert outcome.error_code == LEASE_LOST
    after = client.get(f"{API}/runs/{submitted['run_id']}").json()
    assert after["status"] == "RUNNING"
    # 分类没有被写入。
    assert client.get(f"{API}/tickets/{submitted['ticket_id']}").json()["category"] is None


def test_claim_next_skips_rows_locked_by_another_worker(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    """``FOR UPDATE SKIP LOCKED`` 的实质验证：并发 Worker 不会互相阻塞或重复领取。"""
    first = _submit(client, logged_in_customer, "skip-key-0001")
    second = _submit(client, logged_in_customer, "skip-key-0002")

    with session_scope() as holder:
        held = SqlAlchemyRunRepository(holder).claim_next(owner="worker-a", lease_seconds=60)
        assert held is not None
        # holder 尚未提交，行锁仍被持有。另一个会话必须跳过它领到另一条。
        with session_scope() as other:
            claimed = SqlAlchemyRunRepository(other).claim_next(
                owner="worker-b", lease_seconds=60
            )
        assert claimed is not None
        assert claimed.id != held.id
        assert {str(held.id), str(claimed.id)} == {first["run_id"], second["run_id"]}


# --- SSE 事件流 -------------------------------------------------------------


def test_sse_stream_replays_events_and_closes_at_terminal_state(
    client: TestClient,
    demo_users: None,
    indexed_knowledge: None,
    logged_in_customer: str,
) -> None:
    submitted = _submit(client, logged_in_customer, "sse-key-0001")
    assert _run_worker_once() is True

    response = client.get(f"{API}/runs/{submitted['run_id']}/events")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    # 禁用中间层缓冲，否则事件会被攒到流结束才下发。
    assert response.headers["cache-control"] == "no-cache, no-transform"
    assert response.headers["x-accel-buffering"] == "no"

    body = response.text
    assert body.startswith("retry: 3000")
    frames = parse_sse(body)

    names = [name for _, name, _ in frames]
    assert names[0] == "run.started"
    assert names[-1] == "stream.closed"
    assert "run.completed" in names
    assert "retrieval.completed" in names
    assert "draft.created" in names
    assert names.count("run.step.completed") == HAPPY_PATH_STEPS

    ids = [event_id for event_id, _, _ in frames if event_id is not None]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))

    closed = frames[-1][2]
    assert closed["status"] == "COMPLETED"
    assert closed["reason"] == "terminal"

    completed = next(data for _, name, data in frames if name == "run.completed")
    # ``data`` 是自描述信封；业务字段在 payload 里。
    payload = completed["payload"]
    assert isinstance(payload, dict)
    assert payload["category"] == "DELIVERY"
    assert payload["category_label"] == "配送物流"


def test_sse_resumes_from_last_event_id(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    """断线重连不得重新生成或重复发送已推送的事件。"""
    submitted = _submit(client, logged_in_customer, "sse-key-0002")
    assert _run_worker_once() is True
    url = f"{API}/runs/{submitted['run_id']}/events"

    full = parse_sse(client.get(url).text)
    assert len(full) >= 3
    first_event_id = full[0][0]
    assert first_event_id is not None

    resumed = parse_sse(client.get(url, headers={"Last-Event-ID": str(first_event_id)}).text)
    # 已确认过的事件不会被重发，且后续内容与完整流一致。
    assert resumed[0][0] != first_event_id
    assert [frame[0] for frame in resumed] == [frame[0] for frame in full[1:]]


def test_sse_after_query_is_equivalent_to_last_event_id_header(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    submitted = _submit(client, logged_in_customer, "sse-key-0003")
    assert _run_worker_once() is True
    url = f"{API}/runs/{submitted['run_id']}/events"

    full = parse_sse(client.get(url).text)
    cursor = full[1][0]
    by_header = parse_sse(client.get(url, headers={"Last-Event-ID": str(cursor)}).text)
    by_query = parse_sse(client.get(f"{url}?after={cursor}").text)
    assert [f[0] for f in by_header] == [f[0] for f in by_query]


def test_sse_rejects_invalid_last_event_id(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    submitted = _submit(client, logged_in_customer, "sse-key-0004")
    response = client.get(
        f"{API}/runs/{submitted['run_id']}/events", headers={"Last-Event-ID": "abc"}
    )
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_request"


def test_sse_requires_session(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    submitted = _submit(client, logged_in_customer, "sse-key-0005")
    client.post(f"{API}/auth/logout", headers={"X-CSRF-Token": logged_in_customer})
    response = client.get(f"{API}/runs/{submitted['run_id']}/events")
    # 鉴权发生在响应头发送之前，因此拿到的是规范错误而不是空流。
    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"


def test_sse_hides_other_users_runs(
    client: TestClient,
    demo_users: None,
    logged_in_customer: str,
    create_user: Callable[..., str],
) -> None:
    submitted = _submit(client, logged_in_customer, "sse-key-0006")
    create_user("someone@example.com", Role.USER)
    client.post(f"{API}/auth/logout", headers={"X-CSRF-Token": logged_in_customer})
    client.post(
        f"{API}/auth/login", json={"email": "someone@example.com", "password": "demo1234"}
    )

    response = client.get(f"{API}/runs/{submitted['run_id']}/events")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")


def test_unknown_run_returns_404(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    assert client.get(f"{API}/runs/{uuid4()}").status_code == 404


# --- 事件契约 ---------------------------------------------------------------


def test_run_json_payload_uses_string_ids_and_iso_timestamps(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    """主键一律序列化为字符串、时间为 ISO 8601 —— 前端不面对 number 精度陷阱。"""
    submitted = _submit(client, logged_in_customer, "sse-key-0007")
    run = client.get(f"{API}/runs/{submitted['run_id']}").json()
    assert isinstance(run["id"], str)
    assert isinstance(run["ticket_id"], str)
    assert run["id"] == submitted["run_id"]
    assert "T" in run["created_at"]
    assert "events" not in run


def test_unsupported_model_mode_endpoint_rejects_real(
    client: TestClient,
    demo_users: None,
    logged_in_customer: str,
    login: Callable[..., str],
) -> None:
    submitted = _submit(client, logged_in_customer, "mode-key-0001")
    assert _run_worker_once() is True
    client.post(f"{API}/auth/logout", headers={"X-CSRF-Token": logged_in_customer})
    staff_csrf = login("agent@example.com")

    response = client.post(
        f"{API}/tickets/{submitted['ticket_id']}/runs",
        json={"model_mode": "real"},
        headers={"X-CSRF-Token": staff_csrf, "Idempotency-Key": "mode-run-key-0001"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "model_mode_unavailable"


def test_http_error_shape_is_problem_details(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    response = client.get(f"{API}/tickets/{uuid4()}")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    payload = response.json()
    assert set(payload) >= {"title", "status", "code", "request_id", "instance"}
    assert payload["status"] == 404
    assert payload["instance"] == response.request.url.path


def test_unhandled_exception_does_not_leak_internals(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    """底层异常文本不外泄：422 的错误响应里只回结构化字段。"""
    response = client.post(
        f"{API}/tickets",
        json={"subject": "", "body": ""},
        headers={"X-CSRF-Token": logged_in_customer, "Idempotency-Key": "tiny-key-000001"},
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == "validation_failed"
    assert payload["request_id"]
    for error in payload["errors"]:
        assert set(error) == {"location", "message", "type"}
