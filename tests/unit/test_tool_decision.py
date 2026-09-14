"""工具注册表与工具决策解析的单测。

对齐 PLAN.md §4：非法参数与权限错误不重试；高风险工具不得进入只读执行循环。
"""

from __future__ import annotations

import json

import pytest

from supportflow.agent.application.tools import (
    MAX_TOOL_CALLS,
    TOOL_REGISTRY,
    ToolRisk,
    build_tool_decision_request,
    parse_tool_decision,
    validate_arguments,
)
from supportflow.model.domain.gateway import ChatRequest
from supportflow.shared.errors import ModelResponseInvalid


def _payload(**fields: object) -> str:
    return json.dumps(fields, ensure_ascii=False)


def test_registry_marks_closing_and_transfer_as_high_risk() -> None:
    """关闭与转派永远是 HIGH_RISK，只能创建审批请求。"""
    assert TOOL_REGISTRY["request_close"].risk is ToolRisk.HIGH_RISK
    assert TOOL_REGISTRY["request_transfer"].risk is ToolRisk.HIGH_RISK
    assert TOOL_REGISTRY["request_close"].requires_approval is True
    assert TOOL_REGISTRY["search_knowledge"].requires_approval is False


def test_tool_call_limit_is_eight() -> None:
    assert MAX_TOOL_CALLS == 8


def test_null_tool_means_no_tool_requested() -> None:
    decision = parse_tool_decision(_payload(tool=None))
    assert decision.tool is None
    assert decision.arguments == {}


def test_missing_tool_key_is_treated_as_no_request() -> None:
    """Mock 网关只输出分类 JSON；缺少 tool 字段表示未请求工具，而不是格式错误。"""
    decision = parse_tool_decision(_payload(category="DELIVERY", confidence=0.7))
    assert decision.tool is None


def test_read_only_tool_with_arguments_is_parsed() -> None:
    decision = parse_tool_decision(
        _payload(tool="search_knowledge", arguments={"query": "物流延误"})
    )
    assert decision.tool == "search_knowledge"
    assert decision.arguments == {"query": "物流延误"}


def test_high_risk_tool_is_rejected_even_when_model_asks_for_it() -> None:
    with pytest.raises(ModelResponseInvalid) as excinfo:
        parse_tool_decision(_payload(tool="request_close", arguments={"reason": "客户要求"}))
    assert "高风险" in str(excinfo.value)


def test_unregistered_tool_is_rejected() -> None:
    with pytest.raises(ModelResponseInvalid):
        parse_tool_decision(_payload(tool="drop_database"))


def test_non_object_json_is_rejected() -> None:
    with pytest.raises(ModelResponseInvalid):
        parse_tool_decision("[1, 2, 3]")


def test_malformed_json_is_rejected() -> None:
    with pytest.raises(ModelResponseInvalid):
        parse_tool_decision("not json at all")


def test_tool_field_must_be_string_or_null() -> None:
    with pytest.raises(ModelResponseInvalid):
        parse_tool_decision(_payload(tool=42))


def test_arguments_reject_unknown_keys_instead_of_trimming() -> None:
    """工单归属由服务端注入，模型传入 ticket_id 必须判为非法而不是被静默忽略。"""
    with pytest.raises(ModelResponseInvalid) as excinfo:
        validate_arguments({"query": "物流", "ticket_id": "someone-else"})
    assert "不允许的字段" in str(excinfo.value)


def test_arguments_require_string_values() -> None:
    with pytest.raises(ModelResponseInvalid):
        validate_arguments({"query": ["物流"]})


def test_arguments_accept_none_as_empty() -> None:
    assert validate_arguments(None) == {}


def test_decision_request_uses_json_response_format() -> None:
    request = build_tool_decision_request(
        subject="快递一直没到", body_cleaned="物流无更新", category="DELIVERY", evidence_count=0
    )
    assert isinstance(request, ChatRequest)
    assert request.response_format == "json"
    assert request.temperature == 0.0
    assert "search_knowledge" in request.messages[0].content
