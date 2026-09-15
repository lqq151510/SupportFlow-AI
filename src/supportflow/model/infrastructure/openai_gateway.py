"""OpenAI-compatible 聊天网关（真实模式）。

三条硬约束：

1. **显式超时**：默认 30 秒，来自 ``Settings.model_request_timeout_seconds``。
2. **错误分类决定要不要重试**：见 ``openai_http`` 的规则表 —— 两个网关共用同一份分类。
3. **真实模式失败绝不降级为 Mock**：本类不持有 Mock 网关，也无任何回退分支。

``response_format=json`` 会映射为 OpenAI 的 ``{"type": "json_object"}``；本仓库的分类与
工具决策节点依赖它，因此连接测试会显式验证这一契约。
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from supportflow.model.domain.gateway import (
    ChatCompletion,
    ChatMessage,
    ChatModelGateway,
    ChatRequest,
    ChatUsage,
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

CHAT_COMPLETIONS_PATH = "/chat/completions"


class OpenAICompatibleChatGateway(ChatModelGateway):
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model_name: str,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._http = OpenAICompatibleHttpClient(
            base_url=base_url, api_key=api_key, timeout_seconds=timeout_seconds, client=client
        )
        self._model_name = model_name

    @property
    def mode(self) -> ModelMode:
        return ModelMode.REAL

    @property
    def model_name(self) -> str:
        return self._model_name

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> OpenAICompatibleChatGateway:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def complete(self, request: ChatRequest) -> ChatCompletion:
        payload: dict[str, object] = {
            "model": self._model_name,
            "messages": [
                {"role": message.role, "content": message.content} for message in request.messages
            ],
            "temperature": request.temperature,
        }
        if request.response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        started = time.perf_counter()
        response = self._http.post(CHAT_COMPLETIONS_PATH, payload)
        latency_ms = int((time.perf_counter() - started) * 1000)

        self._http.check_status(response)
        return self._parse(response, latency_ms=latency_ms)

    def _parse(self, response: httpx.Response, *, latency_ms: int) -> ChatCompletion:
        try:
            body = response.json()
        except ValueError as exc:
            raise ModelResponseInvalid("模型返回的不是合法 JSON") from exc
        if not isinstance(body, dict):
            raise ModelResponseInvalid("模型返回的不是 JSON 对象")

        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ModelResponseInvalid("模型返回缺少 choices")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not isinstance(message, dict):
            raise ModelResponseInvalid("模型返回缺少 message")
        content = message.get("content")
        if not isinstance(content, str):
            raise ModelResponseInvalid("模型返回的 content 不是字符串")

        usage_raw = body.get("usage")
        usage: dict[str, Any] = usage_raw if isinstance(usage_raw, dict) else {}
        logger.info(
            "real model call: model=%s latency_ms=%d prompt_tokens=%s completion_tokens=%s",
            self._model_name,
            latency_ms,
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
        )
        return ChatCompletion(
            text=content,
            model_name=str(body.get("model") or self._model_name),
            mode=ModelMode.REAL,
            usage=ChatUsage(
                prompt_tokens=_as_int(usage.get("prompt_tokens")),
                completion_tokens=_as_int(usage.get("completion_tokens")),
            ),
        )


def _as_int(value: object) -> int:
    return value if isinstance(value, int) else 0


def probe_chat_completion(
    gateway: OpenAICompatibleChatGateway,
    *,
    prompt: str = '只输出一个 JSON 对象：{"ok": true}',
) -> tuple[bool, str]:
    """连接测试用的最小调用，并校验 JSON 契约是否真的可用。

    返回 ``(是否满足契约, 说明)``。**不抛出**：连接测试的语义是「报告结果」，
    而不是把上游错误抛给调用方。
    """
    try:
        completion = gateway.complete(
            ChatRequest(
                messages=(ChatMessage(role="user", content=prompt),),
                temperature=0.0,
                response_format="json",
            )
        )
    except (
        ModelUnavailable,
        ModelAuthenticationFailed,
        ModelRequestRejected,
        ModelResponseInvalid,
    ) as exc:
        # 上游原始说明只在这里（管理员专用诊断）对外可见。
        suffix = f"（上游：{exc.upstream_message}）" if exc.upstream_message else ""
        return False, f"{exc.code}: {exc.detail or exc.title}{suffix}"

    try:
        json.loads(completion.text)
    except json.JSONDecodeError:
        return False, (
            "model_json_contract_unsatisfied: 模型未按 response_format=json 返回可解析 JSON"
        )
    return True, f"ok model={completion.model_name}"
