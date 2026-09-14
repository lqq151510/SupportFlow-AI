"""知识导入与混合检索的 PostgreSQL 集成覆盖。"""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from tests.conftest import API


def _headers(csrf: str, key: str) -> dict[str, str]:
    return {"X-CSRF-Token": csrf, "Idempotency-Key": key}


def _import_document(client: TestClient, csrf: str, key: str, content: bytes):
    return client.post(
        f"{API}/knowledge/imports",
        files={"file": ("refund.md", content, "text/markdown")},
        headers=_headers(csrf, key),
    )


def test_admin_imports_deduplicates_and_hybrid_searches(
    client: TestClient, logged_in_admin: str
) -> None:
    content = "# 退款政策\n订单退款到账通常需要三个工作日。"
    first = _import_document(client, logged_in_admin, "knowledge-key-0001", content.encode())
    replay = _import_document(client, logged_in_admin, "knowledge-key-0001", content.encode())
    duplicate = _import_document(client, logged_in_admin, "knowledge-key-0002", content.encode())

    assert first.status_code == replay.status_code == duplicate.status_code == 202
    assert first.json() == replay.json()
    assert first.json()["status"] == "COMPLETED"
    assert first.json()["duplicate"] is False
    assert duplicate.json()["duplicate"] is True

    found = client.get(f"{API}/knowledge/search", params={"query": "退款到账", "limit": 5})
    assert found.status_code == 200, found.text
    item = found.json()["items"][0]
    assert item["source_type"] == "KNOWLEDGE"
    assert item["source_id"]
    assert item["chunk_id"]
    assert item["source_version"] == "mock-v1"
    assert item["rank_no"] == 1
    assert item["full_text_rank"] is not None
    assert item["vector_rank"] is not None
    assert "退款" in item["quote_text"]


def test_history_import_is_retrievable_with_source_reference(
    client: TestClient, logged_in_admin: str
) -> None:
    payload = (
        "source_ref,question,resolution,resolved_at\n"
        "T-2026-0001,物流一直不动怎么办,核实后补发并告知客户,2026-09-12T08:00:00Z\n"
    )
    imported = client.post(
        f"{API}/history/imports",
        files={"file": ("history.csv", payload.encode(), "text/csv")},
        headers=_headers(logged_in_admin, "history-key-00001"),
    )
    assert imported.status_code == 202, imported.text
    assert imported.json()["kind"] == "HISTORY"

    found = client.get(f"{API}/knowledge/search", params={"query": "物流不动"})
    assert found.status_code == 200
    item = found.json()["items"][0]
    assert item["source_type"] == "HISTORY"
    assert item["locator"] == "T-2026-0001"
    assert item["chunk_id"] is None


def test_non_admin_cannot_import_and_customer_cannot_search(
    client: TestClient,
    logged_in_agent: str,
    login: Callable[..., str],
) -> None:
    forbidden_import = _import_document(
        client,
        logged_in_agent,
        "agent-import-key-1",
        b"refund policy",
    )
    assert forbidden_import.status_code == 403

    customer_csrf = login("customer@example.com")
    forbidden_search = client.get(f"{API}/knowledge/search", params={"query": "退款"})
    assert forbidden_search.status_code == 403
    assert customer_csrf


def test_document_rejects_mismatched_mime_and_reused_key(
    client: TestClient, logged_in_admin: str
) -> None:
    mismatch = client.post(
        f"{API}/knowledge/imports",
        files={"file": ("refund.pdf", b"not-a-pdf", "text/plain")},
        headers=_headers(logged_in_admin, "mime-key-0000001"),
    )
    assert mismatch.status_code == 400

    _import_document(client, logged_in_admin, "same-key-0000001", b"first document")
    conflict = _import_document(client, logged_in_admin, "same-key-0000001", b"second document")
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "idempotency_key_reused"
