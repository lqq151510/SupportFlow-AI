"""会话、Cookie 与 CSRF 的接口级测试。"""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from tests.conftest import API


def test_login_sets_httponly_session_and_readable_csrf_cookie(
    client: TestClient, demo_users: None, login: Callable[..., str]
) -> None:
    login("customer@example.com")
    session_cookie = next(
        cookie for cookie in client.cookies.jar if cookie.name == "sf_session"
    )
    csrf_cookie = next(cookie for cookie in client.cookies.jar if cookie.name == "sf_csrf")
    # 会话 Cookie 必须 HttpOnly；CSRF Cookie 必须可读，否则前端拿不到令牌。
    assert session_cookie.has_nonstandard_attr("HttpOnly")
    assert not csrf_cookie.has_nonstandard_attr("HttpOnly")


def test_login_response_never_contains_password_or_token_hash(
    client: TestClient, demo_users: None
) -> None:
    response = client.post(
        f"{API}/auth/login",
        json={"email": "customer@example.com", "password": "demo1234"},
    )
    body = response.text
    assert "demo1234" not in body
    assert "$argon2" not in body
    assert response.json()["role"] == "USER"


def test_login_with_wrong_password_returns_generic_401(
    client: TestClient, demo_users: None
) -> None:
    response = client.post(
        f"{API}/auth/login",
        json={"email": "customer@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    payload = response.json()
    assert payload["code"] == "unauthenticated"
    assert payload["request_id"]


def test_unknown_account_and_wrong_password_return_identical_errors(
    client: TestClient, demo_users: None
) -> None:
    # 不区分二者，避免账号枚举。
    unknown = client.post(
        f"{API}/auth/login", json={"email": "nobody@example.com", "password": "demo1234"}
    )
    wrong = client.post(
        f"{API}/auth/login", json={"email": "customer@example.com", "password": "bad-password"}
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"]


def test_request_id_is_echoed_and_can_be_supplied_by_caller(
    client: TestClient, demo_users: None
) -> None:
    supplied = "req-from-client-0001"
    response = client.get(f"{API}/auth/me", headers={"X-Request-Id": supplied})
    assert response.status_code == 401
    assert response.headers["X-Request-Id"] == supplied
    assert response.json()["request_id"] == supplied


def test_me_requires_session(client: TestClient, demo_users: None) -> None:
    response = client.get(f"{API}/auth/me")
    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"


def test_me_returns_principal_after_login(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    response = client.get(f"{API}/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "customer@example.com"
    assert response.json()["is_staff"] is False


def test_agent_principal_is_staff(
    client: TestClient, demo_users: None, logged_in_agent: str
) -> None:
    response = client.get(f"{API}/auth/me")
    assert response.json()["is_staff"] is True
    assert response.json()["role"] == "AGENT"


def test_write_without_csrf_header_is_rejected(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    """有会话但没带 CSRF 令牌的写请求必须 403，且错误码可区分。"""
    response = client.post(
        f"{API}/tickets",
        json={"subject": "测试", "body": "正文内容足够长"},
        headers={"Idempotency-Key": "key-without-csrf"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"


def test_write_with_wrong_csrf_token_is_rejected(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    response = client.post(
        f"{API}/tickets",
        json={"subject": "测试", "body": "正文内容足够长"},
        headers={"Idempotency-Key": "key-bad-csrf", "X-CSRF-Token": "not-the-right-token"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"


def test_logout_revokes_session(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    logout = client.post(f"{API}/auth/logout", headers={"X-CSRF-Token": logged_in_customer})
    assert logout.status_code == 204
    assert client.get(f"{API}/auth/me").status_code == 401


def test_healthz_is_open(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "model_mode": "mock"}
