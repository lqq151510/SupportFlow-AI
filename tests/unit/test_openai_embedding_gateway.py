"""OpenAI-compatible Embedding 网关单测（HTTP 层用 respx 拦截）。

两个重点：

1. **维度校验**：索引版本按「模型 + 维度」界定，声明与实际的差异必须被发现；
2. **与聊天网关共用错误分类**：同一份 ``openai_http`` 规则，不重试语义不能分歧。
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from supportflow.model.domain.gateway import ModelMode
from supportflow.model.infrastructure.openai_embedding_gateway import (
    MAX_BATCH_SIZE,
    OpenAICompatibleEmbeddingGateway,
    probe_embedding,
)
from supportflow.shared.errors import (
    ModelAuthenticationFailed,
    ModelRequestRejected,
    ModelResponseInvalid,
    ModelUnavailable,
)

BASE_URL = "https://embed.example.com/v1"
ENDPOINT = f"{BASE_URL}/embeddings"
API_KEY = "sk-embed-unit-test"


def _gateway(*, dimensions: int | None = None) -> OpenAICompatibleEmbeddingGateway:
    return OpenAICompatibleEmbeddingGateway(
        base_url=BASE_URL,
        api_key=API_KEY,
        model_name="BAAI/bge-m3",
        timeout_seconds=5.0,
        dimensions=dimensions,
    )


def _body(*vectors: int, model: str = "BAAI/bge-m3") -> dict[str, object]:
    """按给定维度造返回体。``_body(4, 4)`` 表示两条 4 维向量。"""
    return {
        "model": model,
        "data": [
            {"index": index, "embedding": [0.1] * dim} for index, dim in enumerate(vectors)
        ],
        "usage": {"prompt_tokens": 7},
    }


def test_reports_real_mode_and_model_name() -> None:
    gateway = _gateway()
    assert gateway.mode is ModelMode.REAL
    assert gateway.model_name == "BAAI/bge-m3"


def test_successful_embed_parses_vectors_and_dimension() -> None:
    with respx.mock:
        respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json=_body(1024, 1024)))
        result = _gateway().embed(["物流延误", "退货政策"])

    assert len(result.vectors) == 2
    assert result.dimension == 1024
    assert result.model_name == "BAAI/bge-m3"
    assert result.mode is ModelMode.REAL
    assert result.usage.prompt_tokens == 7


def test_request_sends_model_and_input_without_dimensions_by_default() -> None:
    """默认不下发 ``dimensions``：部分提供方（如 bge-m3）不支持该参数，无条件下发会被拒。"""
    with respx.mock:
        route = respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json=_body(4)))
        _gateway().embed(["文本"])
        payload = json.loads(route.calls[0].request.content)

    assert payload["model"] == "BAAI/bge-m3"
    assert payload["input"] == ["文本"]
    assert "dimensions" not in payload


def test_request_sends_dimensions_when_configured() -> None:
    with respx.mock:
        route = respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json=_body(1024)))
        _gateway(dimensions=1024).embed(["文本"])
        payload = json.loads(route.calls[0].request.content)

    assert payload["dimensions"] == 1024


def test_authorization_header_carries_the_key() -> None:
    with respx.mock:
        route = respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json=_body(4)))
        _gateway().embed(["文本"])
        request = route.calls[0].request

    assert request.headers["authorization"] == f"Bearer {API_KEY}"


def test_inconsistent_dimensions_within_one_batch_is_rejected() -> None:
    with respx.mock:
        respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json=_body(4, 8)))
        with pytest.raises(ModelResponseInvalid) as excinfo:
            _gateway().embed(["甲", "乙"])

    assert "不一致的维度" in str(excinfo.value)


def test_vector_count_mismatch_is_rejected() -> None:
    """返回条数与输入不符时不能挑一条用 —— 那会把向量配错文本。"""
    with respx.mock:
        respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json=_body(4)))
        with pytest.raises(ModelResponseInvalid) as excinfo:
            _gateway().embed(["甲", "乙"])

    assert "条数与输入不符" in str(excinfo.value)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"data": []},
        {"data": [{}]},
        {"data": [{"embedding": []}]},
        {"data": [{"embedding": ["a", "b"]}]},
        {"data": "not-a-list"},
    ],
)
def test_malformed_shapes_are_rejected(body: object) -> None:
    with respx.mock:
        respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json=body))
        with pytest.raises(ModelResponseInvalid):
            _gateway().embed(["文本"])


def test_non_json_body_is_rejected() -> None:
    with respx.mock:
        respx.post(ENDPOINT).mock(return_value=httpx.Response(200, text="<html>oops</html>"))
        with pytest.raises(ModelResponseInvalid):
            _gateway().embed(["文本"])


def test_empty_input_is_rejected_without_calling_upstream() -> None:
    with respx.mock:
        route = respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json=_body(4)))
        with pytest.raises(ModelResponseInvalid):
            _gateway().embed([])

    assert not route.called


def test_oversized_batch_is_rejected_before_calling_upstream() -> None:
    texts = [f"文本-{index}" for index in range(MAX_BATCH_SIZE + 1)]
    with respx.mock:
        route = respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json=_body(4)))
        with pytest.raises(ModelRequestRejected):
            _gateway().embed(texts)

    assert not route.called


# --- 与聊天网关共用的错误分类 -------------------------------------------------


@pytest.mark.parametrize("status", [429, 500, 503])
def test_transient_failures_are_retryable(status: int) -> None:
    with respx.mock:
        respx.post(ENDPOINT).mock(return_value=httpx.Response(status, json={"error": "later"}))
        with pytest.raises(ModelUnavailable):
            _gateway().embed(["文本"])


def test_quota_exhausted_is_not_retryable() -> None:
    """智谱实测形状：429 + code=1113。Embedding 与聊天必须得到同样的判定。"""
    body = {"error": {"code": "1113", "message": "余额不足或无可用资源包,请充值。"}}
    with respx.mock:
        respx.post(ENDPOINT).mock(return_value=httpx.Response(429, json=body))
        with pytest.raises(ModelRequestRejected) as excinfo:
            _gateway().embed(["文本"])

    assert "额度或余额不足" in (excinfo.value.detail or "")


def test_auth_failure_is_not_retryable() -> None:
    with respx.mock:
        respx.post(ENDPOINT).mock(return_value=httpx.Response(401, json={"error": "bad key"}))
        with pytest.raises(ModelAuthenticationFailed) as excinfo:
            _gateway().embed(["文本"])

    assert API_KEY not in str(excinfo.value)


def test_timeout_is_retryable() -> None:
    with respx.mock:
        respx.post(ENDPOINT).mock(side_effect=httpx.ConnectTimeout("slow"))
        with pytest.raises(ModelUnavailable):
            _gateway().embed(["文本"])


# --- 连接测试探针 -------------------------------------------------------------


def test_probe_accepts_matching_dimension() -> None:
    with respx.mock:
        respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json=_body(1024)))
        ok, detail = probe_embedding(_gateway(), expected_dim=1024)

    assert ok is True
    assert "dim=1024" in detail


def test_probe_flags_dimension_mismatch() -> None:
    """声明 1024 而模型返回 768：必须在配置阶段就报出来，而不是建出错误的向量列。"""
    with respx.mock:
        respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json=_body(768)))
        ok, detail = probe_embedding(_gateway(), expected_dim=1024)

    assert ok is False
    assert detail.startswith("embedding_dim_mismatch")
    assert "1024" in detail and "768" in detail


def test_probe_reports_upstream_error_without_raising() -> None:
    body = {"error": {"code": "1113", "message": "余额不足或无可用资源包,请充值。"}}
    with respx.mock:
        respx.post(ENDPOINT).mock(return_value=httpx.Response(429, json=body))
        ok, detail = probe_embedding(_gateway(), expected_dim=1024)

    assert ok is False
    assert detail.startswith("model_request_rejected")
    assert "余额不足" in detail
