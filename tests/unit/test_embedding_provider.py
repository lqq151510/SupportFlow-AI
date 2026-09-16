"""组合根嵌入适配器单测。

两条行为必须钉住：

1. **未配置 ≠ 降级**：没有启用 Embedding 配置时用确定性 Mock（旧版索引版本），
   这是「未配置」而不是「真实失败后回退」；
2. **配置了就必须一致**：索引版本名由「模型 + 维度」派生，且维度与配置声明不符时
   直接失败 —— 否则会把不匹配的向量写进库里，而后发现只能整批重建索引。
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import httpx
import pytest
import respx

from supportflow.bootstrap.embedding_provider import ConfiguredEmbeddingProvider
from supportflow.knowledge.domain.index_versions import LEGACY_INDEX_VERSION
from supportflow.knowledge.infrastructure.embedding_providers import MockEmbeddingProvider
from supportflow.model.domain.models import ResolvedEmbeddingConfig
from supportflow.shared.errors import ModelResponseInvalid

BASE_URL = "https://embed.example.com/v1"
ENDPOINT = f"{BASE_URL}/embeddings"
MODEL_NAME = "BAAI/bge-m3"


@dataclass
class _StubModelConfigs:
    """只暴露 `resolve_embedding_config`：适配器只需要这一个能力。"""

    resolved: ResolvedEmbeddingConfig | None

    def resolve_embedding_config(self, config_id: object = None) -> ResolvedEmbeddingConfig | None:
        return self.resolved


def _resolved(dim: int = 1024) -> ResolvedEmbeddingConfig:
    return ResolvedEmbeddingConfig(
        base_url=BASE_URL,
        model_name=MODEL_NAME,
        api_key="sk-unit-test",
        timeout_seconds=5.0,
        embedding_dim=dim,
    )


def _provider(resolved: ResolvedEmbeddingConfig | None) -> ConfiguredEmbeddingProvider:
    return ConfiguredEmbeddingProvider(
        _StubModelConfigs(resolved),  # type: ignore[arg-type]
        fallback=MockEmbeddingProvider(),
    )


def _handler(request: httpx.Request) -> httpx.Response:
    payload = json.loads(request.content)
    count = len(payload["input"])
    return httpx.Response(
        200,
        json={
            "model": MODEL_NAME,
            "data": [{"index": i, "embedding": [0.01] * 1024} for i in range(count)],
            "usage": {"prompt_tokens": 5},
        },
    )


# --- 未配置：旧版确定性 Mock --------------------------------------------------


def test_without_config_falls_back_to_the_legacy_mock_version() -> None:
    provider = _provider(None)
    assert provider.active_index_version().name == LEGACY_INDEX_VERSION
    assert provider.active_index_version().is_legacy


def test_without_config_produces_deterministic_legacy_vectors() -> None:
    provider = _provider(None)
    first = provider.embed(["物流延误"])
    second = provider.embed(["物流延误"])
    assert first == second
    assert len(first[0]) == provider.active_index_version().dimension


def test_without_config_never_calls_the_network() -> None:
    """未配置时必须完全离线 —— 否则测试与本地开发会意外打到上游。"""
    with respx.mock(assert_all_called=False) as router:
        route = router.post(ENDPOINT)
        _provider(None).embed(["物流延误"])
    assert not route.called


def test_empty_input_short_circuits() -> None:
    with respx.mock(assert_all_called=False) as router:
        route = router.post(ENDPOINT)
        assert _provider(_resolved()).embed([]) == []
    assert not route.called


# --- 已配置：真实网关 ---------------------------------------------------------


def test_configured_provider_derives_the_index_version_from_model_and_dimension() -> None:
    spec = _provider(_resolved()).active_index_version()
    assert spec.name == "bge-m3-1024-v1"
    assert spec.embedding_model == MODEL_NAME
    assert spec.dimension == 1024
    assert not spec.is_legacy


@respx.mock
def test_configured_provider_returns_real_vectors() -> None:
    respx.post(ENDPOINT).mock(side_effect=_handler)
    vectors = _provider(_resolved()).embed(["甲", "乙"])
    assert len(vectors) == 2
    assert all(len(vector) == 1024 for vector in vectors)


@respx.mock
def test_configured_provider_does_not_send_the_dimensions_parameter() -> None:
    """**不得**下发 ``dimensions``。

    这是真实调用换来的教训：``BAAI/bge-m3`` 不支持该参数，下发会返回 HTTP 400。
    声明的维度是**校验目标**（见下面的 mismatch 用例），不是请求参数。
    曾经这里有反向断言 —— 那等于给错误的请求形状写了保证书。
    """
    route = respx.post(ENDPOINT).mock(side_effect=_handler)
    _provider(_resolved()).embed(["甲"])
    payload = json.loads(route.calls[0].request.content)
    assert "dimensions" not in payload
    assert payload["model"] == MODEL_NAME
    assert payload["input"] == ["甲"]


@respx.mock
def test_dimension_mismatch_fails_instead_of_writing_wrong_vectors() -> None:
    """模型实际返回 768 维而配置声明 1024 —— 直接失败。

    若放行，写进库的向量与索引版本的维度契约不符，事后只能整批重建索引。
    """

    def _wrong_handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        count = len(payload["input"])
        return httpx.Response(
            200,
            json={"model": MODEL_NAME, "data": [{"index": i, "embedding": [0.01] * 768}
                                               for i in range(count)]},
        )

    respx.post(ENDPOINT).mock(side_effect=_wrong_handler)
    with pytest.raises(ModelResponseInvalid) as excinfo:
        _provider(_resolved()).embed(["甲"])

    assert "embedding_dim_mismatch" in str(excinfo.value)


@respx.mock
def test_upstream_failure_propagates_instead_of_degrading_to_mock() -> None:
    """真实模式失败绝不回退到 Mock —— 否则导入会被静默降级，索引却标着真实模型。"""
    from supportflow.shared.errors import ModelUnavailable

    respx.post(ENDPOINT).mock(return_value=httpx.Response(503, json={"error": "later"}))
    with pytest.raises(ModelUnavailable):
        _provider(_resolved()).embed(["甲"])


@pytest.mark.parametrize(
    ("model", "dim", "expected"),
    [
        ("BAAI/bge-m3", 1024, "bge-m3-1024-v1"),
        ("Qwen/Qwen3-Embedding-8B", 4096, "qwen3-embedding-8b-4096-v1"),
        ("bge_m3", 512, "bge-m3-512-v1"),
    ],
)
def test_index_version_naming_is_stable(model: str, dim: int, expected: str) -> None:
    """名字会进数据库并出现在引用的 `source_version` 里，因此派生规则必须稳定。"""
    from supportflow.knowledge.domain.index_versions import derive_index_version_name

    assert derive_index_version_name(model, dim) == expected
