"""分类目录、分类解析与 Mock 网关之间的一致性。"""

from __future__ import annotations

import json

import pytest

from supportflow.agent.application.classification import (
    build_request,
    parse_classification,
)
from supportflow.model.infrastructure.mock_gateway import MockChatGateway
from supportflow.shared.errors import ModelResponseInvalid
from supportflow.ticket.application.catalog import (
    ALLOWED_CATEGORY_CODES,
    label_of,
    parse_category,
)
from supportflow.ticket.domain.models import CATEGORY_LABELS, TicketCategory


def test_allowed_codes_match_enum_exactly() -> None:
    assert set(ALLOWED_CATEGORY_CODES) == {category.value for category in TicketCategory}
    assert set(CATEGORY_LABELS) == set(TicketCategory)


@pytest.mark.parametrize("code", [category.value for category in TicketCategory])
def test_parse_category_accepts_known_codes(code: str) -> None:
    assert parse_category(code) is TicketCategory(code)


def test_parse_category_normalizes_case_and_padding() -> None:
    assert parse_category("  delivery ") is TicketCategory.DELIVERY


def test_parse_category_returns_none_for_unknown_code() -> None:
    # 未知代码必须返回 None，由调用方判为模型失败 —— 不猜测、不取近似值。
    assert parse_category("REFUND_NOW") is None


def test_label_of_returns_chinese_label() -> None:
    assert label_of(TicketCategory.DELIVERY) == "配送物流"


# --- 分类解析 ---------------------------------------------------------------


def test_build_request_uses_cleaned_body_only() -> None:
    request = build_request(subject="快递没到", body_cleaned="清洗后的正文")
    assert request.temperature == 0.0
    assert request.response_format == "json"
    assert "清洗后的正文" in request.messages[-1].content
    assert "DELIVERY" in request.messages[0].content


def test_parse_classification_reads_structured_output() -> None:
    outcome = parse_classification(
        json.dumps({"category": "ACCOUNT", "confidence": 0.8, "rationale": "提到验证码"})
    )
    assert outcome.category is TicketCategory.ACCOUNT
    assert outcome.confidence == 0.8
    assert outcome.rationale == "提到验证码"


def test_parse_classification_clamps_confidence() -> None:
    assert parse_classification('{"category":"OTHER","confidence":5}').confidence == 1.0
    assert parse_classification('{"category":"OTHER","confidence":-3}').confidence == 0.0


def test_parse_classification_defaults_missing_rationale() -> None:
    assert parse_classification('{"category":"OTHER"}').rationale == ""


@pytest.mark.parametrize(
    "raw",
    [
        "不是 JSON",
        '["OTHER"]',
        '{"confidence":0.9}',
        '{"category":"NOT_A_CATEGORY"}',
        '{"category":"OTHER","confidence":"很高"}',
    ],
)
def test_parse_classification_rejects_invalid_output(raw: str) -> None:
    with pytest.raises(ModelResponseInvalid):
        parse_classification(raw)


# --- Mock 网关与分类枚举的一致性 ---------------------------------------------


def test_mock_gateway_labels_are_all_valid_category_codes() -> None:
    """Mock 网关刻意不导入业务模块，二者的集合一致性只能靠测试交叉断言。"""
    from supportflow.model.infrastructure.mock_gateway import _HINTS

    unknown = set(_HINTS) - set(ALLOWED_CATEGORY_CODES)
    assert not unknown, f"Mock 网关产出了枚举外的标签：{unknown}"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("快递一直没到，物流信息停在上周", TicketCategory.DELIVERY),
        ("我要退货，无理由退换怎么操作", TicketCategory.RETURN_POLICY),
        ("说明书找不到，如何安装这个支架", TicketCategory.PRODUCT_USAGE),
        ("账号登录不了，验证码收不到", TicketCategory.ACCOUNT),
        ("客服态度太差，我要投诉", TicketCategory.COMPLAINT),
        ("今天天气不错", TicketCategory.OTHER),
    ],
)
def test_mock_gateway_end_to_end_classification(text: str, expected: TicketCategory) -> None:
    gateway = MockChatGateway()
    completion = gateway.complete(build_request(subject=text, body_cleaned=text))
    assert parse_classification(completion.text).category is expected


def test_mock_gateway_is_deterministic() -> None:
    gateway = MockChatGateway()
    request = build_request(subject="退货", body_cleaned="我要退货")
    assert gateway.complete(request).text == gateway.complete(request).text
    assert gateway.mode.value == "mock"
