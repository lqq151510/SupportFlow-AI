"""工单接口的集成测试 —— 阶段 2 验收标准的核心。

验收口径：「提交工单 → 持久化 → 刷新后仍可查询」。这里的「刷新」指**在新连接上
重新读取**，所以断言一律走独立请求，而不是复用请求内的对象。
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
from fastapi.testclient import TestClient

from supportflow.identity.domain.models import Role
from tests.conftest import API

SUBJECT = "快递三天没动"
#: 故意混入引用行与签名尾块，用来验证清洗结果确实落库。
BODY = "\n".join(
    [
        "订单 A-2026-0901 一直显示运输中，麻烦帮我查一下",
        "> 系统自动回复：请耐心等待",
        "--",
        "张三",
        "13800000000",
    ]
)


def _submit(client: TestClient, csrf: str, key: str, **overrides: object) -> httpx.Response:
    payload = {"subject": SUBJECT, "body": BODY}
    payload.update(overrides)
    return client.post(
        f"{API}/tickets",
        json=payload,
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": key},
    )


def test_submit_without_idempotency_key_is_rejected(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    response = client.post(
        f"{API}/tickets",
        json={"subject": SUBJECT, "body": BODY},
        headers={"X-CSRF-Token": logged_in_customer},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_request"


def test_submit_with_too_short_idempotency_key_is_rejected(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    response = _submit(client, logged_in_customer, "short")
    assert response.status_code == 400


def test_submit_returns_202_with_run_id(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    response = _submit(client, logged_in_customer, "submit-key-0001")
    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload["status"] == "QUEUED"
    assert payload["ticket_no"].startswith("T-")
    assert payload["model_mode"] == "mock"
    assert response.headers["Location"] == f"{API}/tickets/{payload['ticket_id']}"


def test_submitted_ticket_is_persisted_and_readable_after_refresh(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    submitted = _submit(client, logged_in_customer, "persist-key-0001").json()

    detail = client.get(f"{API}/tickets/{submitted['ticket_id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["ticket_no"] == submitted["ticket_no"]
    assert body["status"] == "OPEN"
    assert body["category"] is None
    assert body["version"] == 1
    assert body["clean_version"] == 1

    # 清洗结果已落库：引用行与签名块被去掉，订单号原样保留。
    assert "订单 A-2026-0901" in body["body_cleaned"]
    assert ">" not in body["body_cleaned"]
    assert "13800000000" not in body["body_cleaned"]

    listing = client.get(f"{API}/tickets").json()
    assert listing["total"] == 1
    assert listing["items"][0]["id"] == submitted["ticket_id"]


def test_replaying_same_key_and_body_returns_original_result(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    first = _submit(client, logged_in_customer, "replay-key-0001")
    second = _submit(client, logged_in_customer, "replay-key-0001")

    assert first.status_code == second.status_code == 202
    assert first.json() == second.json()
    # 关键：没有产生第二张工单。
    assert client.get(f"{API}/tickets").json()["total"] == 1


def test_same_key_with_different_body_is_rejected(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    _submit(client, logged_in_customer, "conflict-key-0001")
    conflict = _submit(client, logged_in_customer, "conflict-key-0001", body="换了内容的正文")
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "idempotency_key_reused"
    assert conflict.json()["scope"] == "POST /api/v1/tickets"


def test_regular_user_cannot_pick_model_mode(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    response = _submit(client, logged_in_customer, "mode-key-0001", model_mode="real")
    assert response.status_code == 403
    assert response.json()["code"] == "model_mode_not_permitted"


def test_agent_can_pick_an_available_model_mode(
    client: TestClient, demo_users: None, logged_in_agent: str
) -> None:
    response = _submit(client, logged_in_agent, "agent-mode-key-01", model_mode="mock")
    assert response.status_code == 202
    assert response.json()["model_mode"] == "mock"


def test_staff_requesting_unimplemented_mode_is_rejected_not_downgraded(
    client: TestClient, demo_users: None, logged_in_agent: str
) -> None:
    """阶段 2 没有真实网关，按次指定 real 必须报错而不是记成 real 由 Mock 执行。"""
    response = _submit(client, logged_in_agent, "agent-mode-key-02", model_mode="real")
    assert response.status_code == 409
    assert response.json()["code"] == "model_mode_unavailable"


def test_unknown_ticket_returns_404(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    response = client.get(f"{API}/tickets/00000000-0000-4000-8000-000000000000")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_malformed_ticket_id_returns_422(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    assert client.get(f"{API}/tickets/not-a-uuid").status_code == 422


def test_other_user_cannot_see_ticket_and_gets_404_not_403(
    client: TestClient,
    demo_users: None,
    logged_in_customer: str,
    create_user: Callable[..., str],
) -> None:
    """跨用户访问返回 404 而不是 403 —— 不泄露「这张工单是否存在」。"""
    submitted = _submit(client, logged_in_customer, "privacy-key-0001").json()

    create_user("other@example.com", Role.USER)
    client.post(f"{API}/auth/logout", headers={"X-CSRF-Token": logged_in_customer})
    relogin = client.post(
        f"{API}/auth/login",
        json={"email": "other@example.com", "password": "demo1234"},
    )
    assert relogin.status_code == 200

    detail = client.get(f"{API}/tickets/{submitted['ticket_id']}")
    assert detail.status_code == 404
    assert detail.json()["code"] == "not_found"

    # 列表里也看不到。
    assert client.get(f"{API}/tickets").json()["total"] == 0


def test_agent_sees_all_tickets_in_workspace(
    client: TestClient,
    demo_users: None,
    logged_in_customer: str,
    login: Callable[..., str],
) -> None:
    _submit(client, logged_in_customer, "staff-visibility-1")
    client.post(f"{API}/auth/logout", headers={"X-CSRF-Token": logged_in_customer})
    login("agent@example.com")

    listing = client.get(f"{API}/tickets").json()
    assert listing["total"] == 1


def test_subject_and_body_length_limits_are_enforced(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    too_long_subject = _submit(
        client, logged_in_customer, "too-long-subject-1", subject="题" * 201
    )
    too_long_body = _submit(client, logged_in_customer, "too-long-body-0001", body="文" * 8001)
    assert too_long_subject.status_code == 422
    assert too_long_body.status_code == 422


def test_submit_without_session_is_rejected(client: TestClient, demo_users: None) -> None:
    response = client.post(
        f"{API}/tickets",
        json={"subject": SUBJECT, "body": BODY},
        headers={"Idempotency-Key": "anonymous-key-01"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"
