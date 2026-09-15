"""OpenAI-compatible 网关单测（HTTP 层用 respx 拦截，不发真实请求）。

重点是**错误分类**，因为它决定要不要重试：

- 超时 / 连接失败 / 429 / 5xx → ``ModelUnavailable``（``with_retries`` 最多再试 3 次）；
- 401 / 403 与其余 4xx → 不可重试的错误码（重试只会放大限流与延迟）；
- 响应结构不符 → ``ModelResponseInvalid``。

同时守住 ``response_format=json`` → ``{"type": "json_object"}`` 的映射：本仓库的分类与
工具决策节点依赖它。
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from supportflow.model.domain.gateway import ChatMessage, ChatRequest, ModelMode
from supportflow.model.infrastructure.openai_gateway import (
    OpenAICompatibleChatGateway,
    probe_chat_completion,
)
from supportflow.shared.errors import (
    ModelAuthenticationFailed,
    ModelRequestRejected,
    ModelResponseInvalid,
    ModelUnavailable,
)

BASE_URL = "https://model.example.com/v1"
ENDPOINT = f"{BASE_URL}/chat/completions"
API_KEY = "sk-unit-test-key"

_OK_BODY = {
    "model": "glm-4-flash",
    "choices": [{"message": {"role": "assistant", "content": '{"category": "DELIVERY"}'}}],
    "usage": {"prompt_tokens": 12, "completion_tokens": 7},
}


def _gateway() -> OpenAICompatibleChatGateway:
    return OpenAICompatibleChatGateway(
        base_url=BASE_URL, api_key=API_KEY, model_name="glm-4-flash", timeout_seconds=5.0
    )


def _request(response_format: str = "text") -> ChatRequest:
    return ChatRequest(
        messages=(ChatMessage(role="user", content="你好"),),
        temperature=0.0,
        response_format=response_format,  # type: ignore[arg-type]
    )


def test_gateway_reports_real_mode_and_configured_model() -> None:
    gateway = _gateway()
    assert gateway.mode is ModelMode.REAL
    assert gateway.model_name == "glm-4-flash"


def test_successful_call_parses_content_model_and_usage() -> None:
    with respx.mock:
        respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json=_OK_BODY))
        completion = _gateway().complete(_request())

    assert completion.text == '{"category": "DELIVERY"}'
    assert completion.model_name == "glm-4-flash"
    assert completion.mode is ModelMode.REAL
    assert completion.usage.prompt_tokens == 12
    assert completion.usage.completion_tokens == 7


def test_authorization_header_carries_the_key() -> None:
    with respx.mock:
        route = respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json=_OK_BODY))
        _gateway().complete(_request())
        request = route.calls[0].request

    assert request.headers["authorization"] == f"Bearer {API_KEY}"
    assert request.headers["content-type"] == "application/json"


def test_json_response_format_is_mapped_to_json_object() -> None:
    with respx.mock:
        route = respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json=_OK_BODY))
        _gateway().complete(_request("json"))
        payload = json.loads(route.calls[0].request.content)

    assert payload["response_format"] == {"type": "json_object"}
    assert payload["model"] == "glm-4-flash"
    assert payload["messages"] == [{"role": "user", "content": "你好"}]
    assert payload["temperature"] == 0.0


def test_text_response_format_sends_no_json_mode() -> None:
    """文本模式不得强行加 json_object，否则部分模型会拒答。"""
    with respx.mock:
        route = respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json=_OK_BODY))
        _gateway().complete(_request("text"))
        payload = json.loads(route.calls[0].request.content)

    assert "response_format" not in payload


@pytest.mark.parametrize("status", [408, 409, 425, 429, 500, 502, 503, 504])
def test_retryable_statuses_raise_model_unavailable(status: int) -> None:
    with respx.mock:
        respx.post(ENDPOINT).mock(return_value=httpx.Response(status, json={"error": "x"}))
        with pytest.raises(ModelUnavailable):
            _gateway().complete(_request())


@pytest.mark.parametrize("status", [401, 403])
def test_auth_failures_are_not_retryable(status: int) -> None:
    with respx.mock:
        respx.post(ENDPOINT).mock(return_value=httpx.Response(status, json={"error": "bad key"}))
        with pytest.raises(ModelAuthenticationFailed) as excinfo:
            _gateway().complete(_request())
    # 错误信息不得回显请求里带过的凭据。
    assert API_KEY not in str(excinfo.value)


@pytest.mark.parametrize("status", [400, 404, 422])
def test_other_client_errors_are_not_retryable(status: int) -> None:
    with respx.mock:
        respx.post(ENDPOINT).mock(return_value=httpx.Response(status, json={"error": "bad"}))
        with pytest.raises(ModelRequestRejected):
            _gateway().complete(_request())


def test_timeout_raises_model_unavailable() -> None:
    with respx.mock:
        respx.post(ENDPOINT).mock(side_effect=httpx.ConnectTimeout("too slow"))
        with pytest.raises(ModelUnavailable):
            _gateway().complete(_request())


def test_connection_error_raises_model_unavailable() -> None:
    with respx.mock:
        respx.post(ENDPOINT).mock(side_effect=httpx.ConnectError("refused"))
        with pytest.raises(ModelUnavailable):
            _gateway().complete(_request())


def test_non_json_body_raises_response_invalid() -> None:
    with respx.mock:
        respx.post(ENDPOINT).mock(return_value=httpx.Response(200, text="<html>oops</html>"))
        with pytest.raises(ModelResponseInvalid):
            _gateway().complete(_request())


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"choices": []},
        {"choices": [{}]},
        {"choices": [{"message": {}}]},
        {"choices": [{"message": {"content": 42}}]},
        "not-an-object",
    ],
)
def test_malformed_shapes_raise_response_invalid(body: object) -> None:
    with respx.mock:
        respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json=body))
        with pytest.raises(ModelResponseInvalid):
            _gateway().complete(_request())


def test_usage_defaults_to_zero_when_absent() -> None:
    body = {"choices": [{"message": {"content": "hi"}}]}
    with respx.mock:
        respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json=body))
        completion = _gateway().complete(_request())

    assert completion.usage.prompt_tokens == 0
    assert completion.usage.completion_tokens == 0


# --- 连接测试探针 -------------------------------------------------------------


def test_probe_reports_success_when_json_contract_is_met() -> None:
    with respx.mock:
        respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json=_OK_BODY))
        ok, detail = probe_chat_completion(_gateway())

    assert ok is True
    assert "glm-4-flash" in detail


def test_probe_flags_json_contract_violation() -> None:
    """模型忽略 response_format 时必须在配置阶段就报出来，而不是等运行转人工。"""
    body = {"choices": [{"message": {"content": "当然可以，这是一段普通文本"}}]}
    with respx.mock:
        respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json=body))
        ok, detail = probe_chat_completion(_gateway())

    assert ok is False
    assert detail.startswith("model_json_contract_unsatisfied")


def test_probe_reports_upstream_error_code_instead_of_raising() -> None:
    with respx.mock:
        respx.post(ENDPOINT).mock(return_value=httpx.Response(401, json={"error": "bad key"}))
        ok, detail = probe_chat_completion(_gateway())

    assert ok is False
    assert detail.startswith("model_auth_failed")


# --- 上游诊断信息 -------------------------------------------------------------


def test_upstream_message_is_captured_from_zhipu_style_envelope() -> None:
    """智谱风格 ``{"error": {"code": ..., "message": ...}}`` —— 实测其 401 就是这个形状。"""
    body = {"error": {"code": "1000", "message": "身份验证失败。"}}
    with respx.mock:
        respx.post(ENDPOINT).mock(return_value=httpx.Response(401, json=body))
        with pytest.raises(ModelAuthenticationFailed) as excinfo:
            _gateway().complete(_request())

    assert excinfo.value.upstream_message == "身份验证失败。"
    # 但它不能出现在错误自身的 detail 里，避免顺着 Problem Details 外泄。
    assert "身份验证失败" not in (excinfo.value.detail or "")


def test_upstream_message_is_captured_from_openai_style_envelope() -> None:
    body = {"error": {"message": "Rate limit reached for gpt-4o", "type": "rate_limit"}}
    with respx.mock:
        respx.post(ENDPOINT).mock(return_value=httpx.Response(429, json=body))
        with pytest.raises(ModelUnavailable) as excinfo:
            _gateway().complete(_request())

    assert excinfo.value.upstream_message == "Rate limit reached for gpt-4o"


def test_unparseable_error_body_leaves_upstream_message_empty() -> None:
    """诊断信息缺失不得影响错误分类。"""
    with respx.mock:
        respx.post(ENDPOINT).mock(return_value=httpx.Response(503, text="<html>gateway</html>"))
        with pytest.raises(ModelUnavailable) as excinfo:
            _gateway().complete(_request())

    assert excinfo.value.upstream_message is None


def test_probe_detail_includes_upstream_message_for_diagnosis() -> None:
    """连接测试是管理员专用路径，这里把上游原话带上，便于定位是密钥、额度还是模型名问题。"""
    body = {"error": {"code": "1000", "message": "身份验证失败。"}}
    with respx.mock:
        respx.post(ENDPOINT).mock(return_value=httpx.Response(401, json=body))
        ok, detail = probe_chat_completion(_gateway())

    assert ok is False
    assert detail.startswith("model_auth_failed")
    assert "身份验证失败。" in detail
