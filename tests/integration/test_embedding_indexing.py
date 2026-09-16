"""真实 Embedding 索引与检索的端到端接线（真实 PostgreSQL + respx 模拟上游）。

本用例证明的是**接线**，而不是模型质量：

1. 启用 Embedding 配置后，导入走真实网关，索引版本由「模型 + 维度」派生；
2. 向量写进**新版专用表**（1024 维），旧列留 NULL（不写垃圾零向量）；
3. 检索走**版本化路线**，引用里的 `source_version` 与索引版本一致；
4. **未配置时仍走旧版 Mock 路线** —— 两条路线都可用，而不是把旧的换掉。

按 AGENTS.md §10，这里只声明「适配器与接线已验证」；真实模型质量需另做评测。
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import httpx
import pytest
import respx
from sqlalchemy import text

from supportflow.bootstrap.container import build_services
from supportflow.identity.domain.models import Principal, Role
from supportflow.identity.infrastructure.repository import SqlAlchemyUserRepository
from supportflow.knowledge.domain.index_versions import LEGACY_INDEX_VERSION
from supportflow.model.domain.models import ModelCapability, ModelProtocol
from supportflow.shared.db import session_scope

EMBEDDING_URL = "https://embed.example.com/v1/embeddings"
MODEL_NAME = "BAAI/bge-m3"
DERIVED_VERSION = "bge-m3-1024-v1"
SECRET = "sk-embed-DO-NOT-LEAK-0123456789"

DOCUMENT = """# 物流延误处理规范

物流长时间未更新时，先核实运单状态；确认异常后为客户补发，并告知新的时效。
若客户要求退款，需转人工确认，不得直接承诺退款金额。

## 退款政策

购买后 30 天内可申请全额退款，需保留原始包装。
"""


def _handler(request: httpx.Request) -> httpx.Response:
    """按请求的输入条数返回同样条数的 1024 维向量。"""
    payload = json.loads(request.content)
    count = len(payload["input"])
    return httpx.Response(
        200,
        json={
            "model": MODEL_NAME,
            "data": [{"index": i, "embedding": [0.02] * 1024} for i in range(count)],
            "usage": {"prompt_tokens": 12},
        },
    )


def _admin() -> Principal:
    with session_scope() as session:
        row = SqlAlchemyUserRepository(session).find_by_email("admin@example.com")
    assert row is not None
    return Principal(
        user_id=row.id, email=row.email, display_name=row.display_name, role=Role(row.role)
    )


def _enable_embedding_config() -> None:
    with session_scope() as session:
        services = build_services(session)
        admin = _admin()
        config = services.model_configs.create(
            admin,
            capability=ModelCapability.EMBEDDING,
            protocol=ModelProtocol.OPENAI_COMPATIBLE,
            base_url="https://embed.example.com/v1",
            model_name=MODEL_NAME,
            api_key=SECRET,
            embedding_dim=1024,
        )
        services.model_configs.enable(admin, config.id)


def _import_document(idempotency_key: str) -> None:
    with session_scope() as session:
        build_services(session).knowledge.import_document(
            _admin(),
            filename="delivery-policy.md",
            content_type="text/markdown",
            raw=DOCUMENT.encode("utf-8"),
            idempotency_key=idempotency_key,
        )


def _rows(sql: str) -> list[tuple[object, ...]]:
    with session_scope() as session:
        return [tuple(row) for row in session.execute(text(sql)).all()]


def _scalar(sql: str) -> object:
    with session_scope() as session:
        return session.execute(text(sql)).scalar()


@pytest.fixture(autouse=True)
def _isolate(demo_users: None, migrated: None) -> Iterator[None]:
    yield


@pytest.mark.integration
def test_import_with_configured_embedding_uses_the_versioned_storage() -> None:
    _enable_embedding_config()

    with respx.mock:
        route = respx.post(EMBEDDING_URL).mock(side_effect=_handler)
        _import_document("embed-import-1")

    assert route.called, "导入应触发真实 Embedding 调用"

    document = _rows(
        "SELECT index_version, embedding_model, embedding_dim FROM knowledge_documents"
    )
    assert document == [(DERIVED_VERSION, MODEL_NAME, 1024)], document

    chunk_count = _scalar("SELECT count(*) FROM knowledge_chunks")
    vector_count = _scalar(
        f"SELECT count(*) FROM knowledge_chunk_vectors WHERE index_version = '{DERIVED_VERSION}'"
    )
    assert chunk_count and vector_count == chunk_count

    # 旧列留 NULL：不写零向量之类的垃圾数据。
    legacy_filled = _scalar("SELECT count(*) FROM knowledge_chunks WHERE embedding IS NOT NULL")
    assert legacy_filled == 0


@pytest.mark.integration
def test_vector_dimension_in_the_new_table_is_1024() -> None:
    _enable_embedding_config()
    with respx.mock:
        respx.post(EMBEDDING_URL).mock(side_effect=_handler)
        _import_document("embed-import-2")

    dimension = _scalar(
        "SELECT vector_dims(embedding) FROM knowledge_chunk_vectors LIMIT 1"
    )
    assert dimension == 1024


@pytest.mark.integration
def test_search_finds_the_document_through_the_versioned_route() -> None:
    _enable_embedding_config()

    with respx.mock:
        respx.post(EMBEDDING_URL).mock(side_effect=_handler)
        _import_document("embed-import-3")

        with session_scope() as session:
            results = build_services(session).knowledge.search(_admin(), "物流延误怎么处理")

    assert results, "版本化检索应能命中刚导入的文档"
    assert {item.citation.source_version for item in results} == {DERIVED_VERSION}


@pytest.mark.integration
def test_the_secret_is_never_returned_by_the_embedding_path() -> None:
    """密钥只以密文入库，且不进入任何检索结果。"""
    _enable_embedding_config()

    with respx.mock:
        respx.post(EMBEDDING_URL).mock(side_effect=_handler)
        _import_document("embed-import-4")
        with session_scope() as session:
            results = build_services(session).knowledge.search(_admin(), "物流")

    payload = json.dumps(
        [
            {"quote": item.citation.quote_text, "version": item.citation.source_version}
            for item in results
        ],
        ensure_ascii=False,
    )
    assert SECRET not in payload

    stored = _scalar("SELECT api_key_ciphertext FROM model_configs LIMIT 1")
    assert isinstance(stored, str) and stored.startswith("v1.") and stored != SECRET


@pytest.mark.integration
def test_without_any_config_the_legacy_mock_route_still_works() -> None:
    """没有 Embedding 配置时走旧版路线：`mock-v1` + 旧列非空。

    两条路线并存（expand-contract），不是把旧的换掉。
    """
    with respx.mock(assert_all_called=False) as router:
        route = router.post(EMBEDDING_URL)
        _import_document("embed-import-5")

    assert not route.called, "未配置时不得调用真实上游"

    document = _rows(
        "SELECT index_version, embedding_model, embedding_dim FROM knowledge_documents"
    )
    assert document == [(LEGACY_INDEX_VERSION, "mock-hash-64", 64)], document

    legacy_filled = _scalar("SELECT count(*) FROM knowledge_chunks WHERE embedding IS NOT NULL")
    assert legacy_filled > 0
    versioned = _scalar("SELECT count(*) FROM knowledge_chunk_vectors")
    assert versioned == 0

    with session_scope() as session:
        results = build_services(session).knowledge.search(_admin(), "物流")
    assert results
    assert {item.citation.source_version for item in results} == {LEGACY_INDEX_VERSION}
