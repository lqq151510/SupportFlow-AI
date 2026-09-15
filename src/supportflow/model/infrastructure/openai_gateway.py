"""OpenAI-compatible 聊天网关（真实模式）。

唯一的模型接入边界在此实现（AGENTS.md §5）。三条硬约束：

1. **显式超时**：默认 30 秒，来自 ``Settings.model_request_timeout_seconds``。
2. **错误分类决定要不要重试**：超时、连接失败、429、5xx → ``ModelUnavailable``（可重试，
   由 ``with_retries`` 做最多 3 次指数退避）；401/403 与其余 4xx → 不可重试的
   ``ModelAuthenticationFailed`` / ``ModelRequestRejected``，重试只会放大限流。
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
    ChatModelGateway,
    ChatRequest,
    ChatUsage,
    ModelMode,
)
from supportflow.shared.errors import (
    AppError,
    ModelAuthenticationFailed,
    ModelRequestRejected,
    ModelResponseInvalid,
    ModelUnavailable,
)

logger = logging.getLogger(__name__)

#: 上游返回「请求本身有问题」时不再重试的状态码。
_RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


class OpenAICompatibleChatGateway(ChatModelGateway):
    """同步 HTTP 网关。

    刻意使用同步客户端：本仓库的业务事务与 Agent 执行都在线程池中同步运行
    （AGENTS.md §5 明确禁止在 ``async def`` 里做阻塞调用，也要求混合时在适配层切换）。
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model_name: str,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model_name = model_name
        self._timeout = timeout_seconds
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(timeout_seconds, connect=min(10.0, timeout_seconds)),
            # 本机 HTTP_PROXY 会劫持请求；模型调用必须直连或走用户显式配置的代理，
            # 因此这里不读环境代理，避免把凭据发给非预期主机。
            trust_env=False,
        )

    @property
    def mode(self) -> ModelMode:
        return ModelMode.REAL

    @property
    def model_name(self) -> str:
        return self._model_name

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def complete(self, request: ChatRequest) -> ChatCompletion:
        payload: dict[str, Any] = {
            "model": self._model_name,
            "messages": [
                {"role": message.role, "content": message.content} for message in request.messages
            ],
            "temperature": request.temperature,
        }
        if request.response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        started = time.perf_counter()
        try:
            response = self._client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise ModelUnavailable(f"模型请求超时（{self._timeout:g}s）") from exc
        except httpx.HTTPError as exc:
            raise ModelUnavailable(f"模型服务连接失败：{type(exc).__name__}") from exc

        latency_ms = int((time.perf_counter() - started) * 1000)
        if response.status_code >= 400:
            self._raise_for_status(response)
        return self._parse(response, latency_ms=latency_ms)

    # --- 内部 ---------------------------------------------------------------

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        """把上游状态码映射为**稳定且可测试**的错误码。错误体不原样外泄。

        上游的原始说明只挂在 ``upstream_message`` 上，供管理员连接测试展示；
        它不会进入普通错误响应（见 ``AppError.upstream_message`` 的说明）。
        """
        status = response.status_code
        upstream = _upstream_message(response)
        if status in (401, 403):
            raise _with_upstream(
                ModelAuthenticationFailed("模型服务拒绝了当前凭据，请检查 API Key 是否有效"),
                upstream,
            )
        if status in _RETRYABLE_STATUS:
            raise _with_upstream(
                ModelUnavailable(f"模型服务暂时不可用（HTTP {status}）"), upstream
            )
        raise _with_upstream(
            ModelRequestRejected(f"模型服务拒绝了该请求（HTTP {status}）"), upstream
        )

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


#: 上游诊断信息保留的最大长度，避免把整页错误文档写进日志或数据库。
_UPSTREAM_MESSAGE_LIMIT = 300


def _upstream_message(response: httpx.Response) -> str | None:
    """抽取上游错误说明，供管理员诊断。

    兼容两种常见信封：OpenAI 风格的 ``{"error": {"message": ...}}``
    与智谱风格 ``{"error": {"code": "1000", "message": "身份验证失败。"}}``。
    解析失败一律返回 ``None`` —— 诊断信息缺失不该影响错误分类。
    """
    try:
        body = response.json()
    except ValueError:
        return None
    if not isinstance(body, dict):
        return None
    error = body.get("error")
    if isinstance(error, dict):
        message = error.get("message") or error.get("msg")
    elif isinstance(error, str):
        message = error
    else:
        message = body.get("message")
    if not isinstance(message, str) or not message.strip():
        return None
    return message.strip()[:_UPSTREAM_MESSAGE_LIMIT]


def _with_upstream(error: AppError, upstream: str | None) -> AppError:
    error.upstream_message = upstream
    return error


def probe_chat_completion(
    gateway: OpenAICompatibleChatGateway,
    *,
    prompt: str = "只输出一个 JSON 对象：{\"ok\": true}",
) -> tuple[bool, str]:
    """连接测试用的最小调用，并校验 JSON 契约是否真的可用。

    返回 ``(是否满足契约, 说明)``。**不抛出**：连接测试的语义是「报告结果」，
    而不是把上游错误抛给调用方。
    """
    from supportflow.model.domain.gateway import ChatMessage

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
