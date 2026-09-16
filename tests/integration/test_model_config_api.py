"""模型配置接口集成测试（真实 PostgreSQL）。

三条重点：

1. **明文 Key 永不回显**：不仅断言响应体里没有它，还直接查库确认落库的是可解密的密文；
2. **同类能力启用互斥**：由 ``(capability) WHERE enabled`` 的部分唯一索引兜底，
   启用新配置后旧配置必须被停用；
3. **连接测试如实报告**：失败时返回稳定错误码，绝不返回 Mock 结果
   （AGENTS.md §10：Mock 与真实结果分别报告）。
"""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import text

from supportflow.model.infrastructure.crypto import AesGcmSecretCipher
from supportflow.shared.db import session_scope
from tests.conftest import API, TEST_MASTER_KEY

#: 刻意做得醒目：一旦出现在任何响应或日志里，测试就会立刻失败。
SECRET = "sk-live-DO-NOT-LEAK-0123456789abcdef"
MODEL_URL = "https://model.example.com/v1"
ENDPOINT = f"{MODEL_URL}/chat/completions"

_OK_BODY = {
    "model": "glm-4-flash",
    "choices": [{"message": {"content": '{"ok": true}'}}],
    "usage": {"prompt_tokens": 3, "completion_tokens": 2},
}


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "capability": "CHAT",
        "base_url": MODEL_URL,
        "model_name": "glm-4-flash",
        "api_key": SECRET,
    }
    payload.update(overrides)
    return payload


def _create(
    client: TestClient, csrf: str, key: str, **overrides: object
) -> httpx.Response:
    return client.post(
        f"{API}/model-configs",
        json=_payload(**overrides),
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": key},
    )


def _ciphertext_in_db(config_id: str) -> str:
    with session_scope() as session:
        value = session.scalar(
            text("SELECT api_key_ciphertext FROM model_configs WHERE id = :id"),
            {"id": config_id},
        )
    assert isinstance(value, str)
    return value


# --- 权限与会话 ---------------------------------------------------------------


def test_requires_authentication(client: TestClient, demo_users: None) -> None:
    assert client.get(f"{API}/model-configs").status_code == 401


@pytest.mark.parametrize("account", ["agent@example.com", "customer@example.com"])
def test_non_admin_cannot_read_or_write(
    client: TestClient, demo_users: None, login: Callable[..., str], account: str
) -> None:
    csrf = login(account)
    assert client.get(f"{API}/model-configs").status_code == 403
    response = _create(client, csrf, f"nonadmin-{account}")
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_write_without_csrf_is_rejected(
    client: TestClient, demo_users: None, logged_in_admin: str
) -> None:
    response = client.post(f"{API}/model-configs", json=_payload())
    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"


# --- 创建与密钥保护 -----------------------------------------------------------


def test_create_stores_ciphertext_and_never_returns_the_key(
    client: TestClient, demo_users: None, logged_in_admin: str
) -> None:
    response = _create(client, logged_in_admin, "model-create-0001")
    assert response.status_code == 201, response.text

    # 响应里连密钥字段都不存在。
    body = response.json()
    assert body["api_key_configured"] is True
    assert "api_key" not in body
    assert SECRET not in response.text

    # 落库的是可解密的密文，而不是明文。
    stored = _ciphertext_in_db(body["id"])
    assert stored != SECRET
    assert stored.startswith("v1.")
    assert AesGcmSecretCipher(TEST_MASTER_KEY).decrypt(stored) == SECRET


def test_list_never_exposes_key_or_ciphertext(
    client: TestClient, demo_users: None, logged_in_admin: str
) -> None:
    created = _create(client, logged_in_admin, "model-list-0001").json()
    stored = _ciphertext_in_db(created["id"])

    response = client.get(f"{API}/model-configs")
    assert response.status_code == 200
    assert SECRET not in response.text
    assert stored not in response.text
    assert response.json()["items"][0]["api_key_configured"] is True


def test_create_rejects_bad_base_url(
    client: TestClient, demo_users: None, logged_in_admin: str
) -> None:
    response = _create(
        client, logged_in_admin, "model-bad-url-1", base_url="model.example.com/v1"
    )
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_request"


def test_missing_master_key_fails_without_writing_anything(
    client: TestClient,
    demo_users: None,
    logged_in_admin: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """主密钥缺失时必须失败，且不得留下任何记录 —— 绝不允许退化为存明文。"""
    from supportflow.shared.config import get_settings

    monkeypatch.setenv("MODEL_SECRET_MASTER_KEY", "")
    get_settings.cache_clear()
    try:
        response = _create(client, logged_in_admin, "model-no-master-1")
        assert response.status_code == 503
        assert response.json()["code"] == "model_config_invalid"
    finally:
        get_settings.cache_clear()

    with session_scope() as session:
        count = session.scalar(text("SELECT count(*) FROM model_configs"))
    assert count == 0


# --- 能力校验 -----------------------------------------------------------------


def test_embedding_requires_dimension(
    client: TestClient, demo_users: None, logged_in_admin: str
) -> None:
    response = _create(
        client, logged_in_admin, "model-emb-0001", capability="EMBEDDING", model_name="bge-m3"
    )
    assert response.status_code == 400


def test_chat_must_not_carry_embedding_dimension(
    client: TestClient, demo_users: None, logged_in_admin: str
) -> None:
    response = _create(client, logged_in_admin, "model-chat-dim-1", embedding_dim=1024)
    assert response.status_code == 400


def test_embedding_config_accepts_dimension(
    client: TestClient, demo_users: None, logged_in_admin: str
) -> None:
    response = _create(
        client,
        logged_in_admin,
        "model-emb-0002",
        capability="EMBEDDING",
        model_name="BAAI/bge-m3",
        embedding_dim=1024,
    )
    assert response.status_code == 201, response.text
    assert response.json()["embedding_dim"] == 1024


# --- 启用互斥 -----------------------------------------------------------------


def test_enabling_a_new_chat_config_disables_the_previous_one(
    client: TestClient, demo_users: None, logged_in_admin: str
) -> None:
    first = _create(client, logged_in_admin, "model-enable-001").json()
    second = _create(
        client, logged_in_admin, "model-enable-002", model_name="glm-4.7-flash"
    ).json()

    assert (
        client.post(
            f"{API}/model-configs/{first['id']}/enable",
            headers={"X-CSRF-Token": logged_in_admin},
        ).status_code
        == 200
    )
    enabled_second = client.post(
        f"{API}/model-configs/{second['id']}/enable",
        headers={"X-CSRF-Token": logged_in_admin},
    )
    assert enabled_second.status_code == 200
    assert enabled_second.json()["enabled"] is True

    items = {item["id"]: item for item in client.get(f"{API}/model-configs").json()["items"]}
    assert items[first["id"]]["enabled"] is False
    assert items[second["id"]]["enabled"] is True

    with session_scope() as session:
        enabled_count = session.scalar(
            text("SELECT count(*) FROM model_configs WHERE capability = 'CHAT' AND enabled")
        )
    assert enabled_count == 1


def test_enable_unknown_config_returns_404(
    client: TestClient, demo_users: None, logged_in_admin: str
) -> None:
    response = client.post(
        f"{API}/model-configs/00000000-0000-0000-0000-000000000000/enable",
        headers={"X-CSRF-Token": logged_in_admin},
    )
    assert response.status_code == 404


# --- 更新 ---------------------------------------------------------------------


def test_updating_api_key_bumps_version_and_replaces_ciphertext(
    client: TestClient, demo_users: None, logged_in_admin: str
) -> None:
    created = _create(client, logged_in_admin, "model-update-001").json()
    before = _ciphertext_in_db(created["id"])
    replacement = "sk-live-ROTATED-9876543210zyxwvu"

    response = client.patch(
        f"{API}/model-configs/{created['id']}",
        json={"api_key": replacement},
        headers={"X-CSRF-Token": logged_in_admin},
    )
    assert response.status_code == 200, response.text
    assert response.json()["version"] == created["version"] + 1
    assert replacement not in response.text

    after = _ciphertext_in_db(created["id"])
    assert after != before
    assert AesGcmSecretCipher(TEST_MASTER_KEY).decrypt(after) == replacement


def test_update_without_api_key_keeps_the_ciphertext(
    client: TestClient, demo_users: None, logged_in_admin: str
) -> None:
    created = _create(client, logged_in_admin, "model-update-002").json()
    before = _ciphertext_in_db(created["id"])

    response = client.patch(
        f"{API}/model-configs/{created['id']}",
        json={"model_name": "glm-4.7-flash"},
        headers={"X-CSRF-Token": logged_in_admin},
    )
    assert response.status_code == 200
    assert response.json()["model_name"] == "glm-4.7-flash"
    assert response.json()["version"] == created["version"]
    assert _ciphertext_in_db(created["id"]) == before


def test_update_unknown_config_returns_404(
    client: TestClient, demo_users: None, logged_in_admin: str
) -> None:
    response = client.patch(
        f"{API}/model-configs/00000000-0000-0000-0000-000000000000",
        json={"model_name": "glm-4.7-flash"},
        headers={"X-CSRF-Token": logged_in_admin},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"model_name": "   "}, "model_name"),
        ({"base_url": "   "}, "base_url"),
    ],
)
def test_update_rejects_blank_text_fields(
    client: TestClient,
    demo_users: None,
    logged_in_admin: str,
    payload: dict[str, str],
    field: str,
) -> None:
    created = _create(client, logged_in_admin, f"model-update-blank-{field}").json()

    response = client.patch(
        f"{API}/model-configs/{created['id']}",
        json=payload,
        headers={"X-CSRF-Token": logged_in_admin},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_request"


def test_chat_update_rejects_embedding_dimension(
    client: TestClient, demo_users: None, logged_in_admin: str
) -> None:
    created = _create(client, logged_in_admin, "model-update-chat-dim").json()

    response = client.patch(
        f"{API}/model-configs/{created['id']}",
        json={"embedding_dim": 1024},
        headers={"X-CSRF-Token": logged_in_admin},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_request"


def test_embedding_dimension_update_is_allowed(
    client: TestClient, demo_users: None, logged_in_admin: str
) -> None:
    created = _create_embedding_config(client, logged_in_admin, "model-update-emb-dim", 1024)

    response = client.patch(
        f"{API}/model-configs/{created['id']}",
        json={"embedding_dim": 768},
        headers={"X-CSRF-Token": logged_in_admin},
    )

    assert response.status_code == 200, response.text
    assert response.json()["embedding_dim"] == 768


# --- 连接测试 -----------------------------------------------------------------


def test_connection_test_unknown_config_returns_404(
    client: TestClient, demo_users: None, logged_in_admin: str
) -> None:
    response = client.post(
        f"{API}/model-configs/00000000-0000-0000-0000-000000000000/test",
        headers={"X-CSRF-Token": logged_in_admin},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_connection_test_reports_success_without_leaking_the_key(
    client: TestClient, demo_users: None, logged_in_admin: str
) -> None:
    created = _create(client, logged_in_admin, "model-test-0001").json()

    with respx.mock:
        route = respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json=_OK_BODY))
        response = client.post(
            f"{API}/model-configs/{created['id']}/test",
            headers={"X-CSRF-Token": logged_in_admin},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["model_name"] == "glm-4-flash"
    assert body["error_code"] is None
    assert SECRET not in response.text

    # 探针确实发出了请求，且用的就是解密后的密钥。
    sent = route.calls[0].request
    assert sent.headers["authorization"] == f"Bearer {SECRET}"
    assert json.loads(sent.content)["response_format"] == {"type": "json_object"}


def test_connection_test_reports_upstream_failure_by_code(
    client: TestClient, demo_users: None, logged_in_admin: str
) -> None:
    created = _create(client, logged_in_admin, "model-test-0002").json()

    with respx.mock:
        respx.post(ENDPOINT).mock(return_value=httpx.Response(401, json={"error": "bad key"}))
        response = client.post(
            f"{API}/model-configs/{created['id']}/test",
            headers={"X-CSRF-Token": logged_in_admin},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "model_auth_failed"


def test_connection_test_flags_missing_json_contract(
    client: TestClient, demo_users: None, logged_in_admin: str
) -> None:
    """模型不支持 response_format=json 时，必须在配置阶段就暴露出来。"""
    created = _create(client, logged_in_admin, "model-test-0003").json()
    body = {"choices": [{"message": {"content": "这是一段普通文本，不是 JSON"}}]}

    with respx.mock:
        respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json=body))
        response = client.post(
            f"{API}/model-configs/{created['id']}/test",
            headers={"X-CSRF-Token": logged_in_admin},
        )

    assert response.json()["ok"] is False
    assert response.json()["error_code"] == "model_json_contract_unsatisfied"


EMBEDDING_URL = "https://embed.example.com/v1/embeddings"


def _embedding_body(dim: int) -> dict[str, object]:
    return {
        "model": "BAAI/bge-m3",
        "data": [{"index": 0, "embedding": [0.01] * dim}],
        "usage": {"prompt_tokens": 5},
    }


def _create_embedding_config(client: TestClient, csrf: str, key: str, dim: int) -> dict:
    response = _create(
        client,
        csrf,
        key,
        capability="EMBEDDING",
        model_name="BAAI/bge-m3",
        base_url="https://embed.example.com/v1",
        embedding_dim=dim,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_embedding_connection_test_accepts_matching_dimension(
    client: TestClient, demo_users: None, logged_in_admin: str
) -> None:
    created = _create_embedding_config(client, logged_in_admin, "model-test-emb-1", 1024)

    with respx.mock:
        respx.post(EMBEDDING_URL).mock(
            return_value=httpx.Response(200, json=_embedding_body(1024))
        )
        response = client.post(
            f"{API}/model-configs/{created['id']}/test",
            headers={"X-CSRF-Token": logged_in_admin},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["error_code"] is None
    assert SECRET not in response.text


def test_embedding_connection_test_flags_dimension_mismatch(
    client: TestClient, demo_users: None, logged_in_admin: str
) -> None:
    """声明 1024 但模型返回 768：必须在配置阶段拦下，否则会建出错误的向量列。"""
    created = _create_embedding_config(client, logged_in_admin, "model-test-emb-2", 1024)

    with respx.mock:
        respx.post(EMBEDDING_URL).mock(
            return_value=httpx.Response(200, json=_embedding_body(768))
        )
        response = client.post(
            f"{API}/model-configs/{created['id']}/test",
            headers={"X-CSRF-Token": logged_in_admin},
        )

    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "embedding_dim_mismatch"
    assert "1024" in body["detail"] and "768" in body["detail"]


def test_embedding_connection_test_reports_quota_problem(
    client: TestClient, demo_users: None, logged_in_admin: str
) -> None:
    """智谱实测：embedding 在免费额度下返回 429 + 余额不足。必须如实报告，不得降级为 Mock。"""
    created = _create_embedding_config(client, logged_in_admin, "model-test-emb-3", 1024)
    error_body = {"error": {"code": "1113", "message": "余额不足或无可用资源包,请充值。"}}

    with respx.mock:
        respx.post(EMBEDDING_URL).mock(return_value=httpx.Response(429, json=error_body))
        response = client.post(
            f"{API}/model-configs/{created['id']}/test",
            headers={"X-CSRF-Token": logged_in_admin},
        )

    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "model_request_rejected"
    assert "余额不足" in body["detail"]
