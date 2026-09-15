"""OpenAI-compatible Embedding 网关（真实模式）。

与聊天网关共用 ``openai_http`` 的错误分类与客户端，因此两个网关在「什么该重试」上
不会有分歧。

**维度是这一层最重要的校验点**：索引版本按「模型 + 维度」界定（AGENTS.md §7），
若配置里写 1024 而模型实际返回 768，建出来的向量列与索引版本就是错的。
因此连接测试会把**实际返回的维度**与配置声明的维度对照，不一致即判定配置不可用 ——
这属于配置错误，重试无意义。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence

import httpx

from supportflow.model.domain.gateway import (
    EmbeddingModelGateway,
    EmbeddingResult,
    EmbeddingUsage,
    ModelMode,
)
from supportflow.model.infrastructure.openai_http import OpenAICompatibleHttpClient
from supportflow.shared.errors import (
    ModelAuthenticationFailed,
    ModelRequestRejected,
    ModelResponseInvalid,
    ModelUnavailable,
)

logger = logging.getLogger(__name__)

EMBEDDINGS_PATH = "/embeddings"

#: 单次批量上限。过大的批量在部分免费额度上会直接被拒，且失败时定位困难。
MAX_BATCH_SIZE = 64


class OpenAICompatibleEmbeddingGateway(EmbeddingModelGateway):
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model_name: str,
        timeout_seconds: float = 30.0,
        dimensions: int | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._http = OpenAICompatibleHttpClient(
            base_url=base_url, api_key=api_key, timeout_seconds=timeout_seconds, client=client
        )
        self._model_name = model_name
        #: 只有显式设置时才下发 ``dimensions``：部分提供方（如 bge-m3）不支持该参数，
        #: 无条件下发会直接被拒。
        self._dimensions = dimensions

    @property
    def mode(self) -> ModelMode:
        return ModelMode.REAL

    @property
    def model_name(self) -> str:
        return self._model_name

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> OpenAICompatibleEmbeddingGateway:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def embed(self, texts: Sequence[str]) -> EmbeddingResult:
        if not texts:
            raise ModelResponseInvalid("Embedding 输入不能为空")
        if len(texts) > MAX_BATCH_SIZE:
            raise ModelRequestRejected(f"单次最多 {MAX_BATCH_SIZE} 条，收到 {len(texts)} 条")

        payload: dict[str, object] = {"model": self._model_name, "input": list(texts)}
        if self._dimensions is not None:
            payload["dimensions"] = self._dimensions

        started = time.perf_counter()
        response = self._http.post(EMBEDDINGS_PATH, payload)
        latency_ms = int((time.perf_counter() - started) * 1000)

        self._http.check_status(response)
        return self._parse(response, expected=len(texts), latency_ms=latency_ms)

    def _parse(
        self, response: httpx.Response, *, expected: int, latency_ms: int
    ) -> EmbeddingResult:
        try:
            body = response.json()
        except ValueError as exc:
            raise ModelResponseInvalid("Embedding 返回的不是合法 JSON") from exc
        if not isinstance(body, dict):
            raise ModelResponseInvalid("Embedding 返回的不是 JSON 对象")

        data = body.get("data")
        if not isinstance(data, list) or not data:
            raise ModelResponseInvalid("Embedding 返回缺少 data")

        vectors: list[list[float]] = []
        for item in data:
            raw = item.get("embedding") if isinstance(item, dict) else None
            if not isinstance(raw, list) or not raw:
                raise ModelResponseInvalid("Embedding 返回的 embedding 不是非空数组")
            try:
                vectors.append([float(value) for value in raw])
            except (TypeError, ValueError) as exc:
                raise ModelResponseInvalid("Embedding 向量包含非数值元素") from exc

        dimensions = {len(vector) for vector in vectors}
        if len(dimensions) != 1:
            # 同一批次内维度不一致说明上游异常，直接失败而不是挑一个用。
            raise ModelResponseInvalid(f"同一批次返回了不一致的维度：{sorted(dimensions)}")
        if len(vectors) != expected:
            raise ModelResponseInvalid(
                f"Embedding 返回条数与输入不符：期望 {expected}，实际 {len(vectors)}"
            )

        usage_raw = body.get("usage")
        usage = usage_raw if isinstance(usage_raw, dict) else {}
        prompt_tokens = usage.get("prompt_tokens")
        logger.info(
            "real embedding call: model=%s batch=%d dim=%d latency_ms=%d",
            self._model_name,
            len(vectors),
            len(vectors[0]),
            latency_ms,
        )
        return EmbeddingResult(
            vectors=vectors,
            model_name=str(body.get("model") or self._model_name),
            mode=ModelMode.REAL,
            usage=EmbeddingUsage(
                prompt_tokens=prompt_tokens if isinstance(prompt_tokens, int) else 0
            ),
        )


def probe_embedding(
    gateway: OpenAICompatibleEmbeddingGateway,
    *,
    expected_dim: int,
    text: str = "物流延误处理规范：核实后补发并告知新的时效。",
) -> tuple[bool, str]:
    """连接测试：跑一次最小批量并**校验实际维度与声明维度一致**。

    返回 ``(是否可用, 说明)``，不抛出 —— 与聊天探针保持同样的语义。
    """
    try:
        result = gateway.embed([text])
    except (
        ModelUnavailable,
        ModelAuthenticationFailed,
        ModelRequestRejected,
        ModelResponseInvalid,
    ) as exc:
        suffix = f"（上游：{exc.upstream_message}）" if exc.upstream_message else ""
        return False, f"{exc.code}: {exc.detail or exc.title}{suffix}"

    if result.dimension != expected_dim:
        return False, (
            f"embedding_dim_mismatch: 配置声明 {expected_dim} 维，模型实际返回 "
            f"{result.dimension} 维。索引版本按维度界定，必须先对齐再建索引。"
        )
    return True, f"ok model={result.model_name} dim={result.dimension}"
