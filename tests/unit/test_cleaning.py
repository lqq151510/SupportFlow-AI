"""工单清洗管线的单测。

重点断言两件事：结构噪声被去掉；**数值与业务标识一个字符都不改**。
"""

from __future__ import annotations

import pytest

from supportflow.ticket.domain.cleaning import CLEAN_VERSION, clean_body


def test_strips_html_tags_and_unescapes_entities() -> None:
    result = clean_body("<p>订单 12345 已到货</p><p>包装破损</p>")
    assert "订单 12345 已到货" in result.text
    assert "包装破损" in result.text
    assert "<" not in result.text


def test_removes_script_and_style_blocks_entirely() -> None:
    raw = "<style>p{color:red}</style><script>alert('x')</script>正文：无法登录"
    result = clean_body(raw)
    assert result.text == "正文：无法登录"


def test_removes_html_comments() -> None:
    assert "隐藏" not in clean_body("正文<!-- 隐藏说明 -->继续").text


def test_unwraps_escaped_angle_brackets() -> None:
    # 实体在标签剥离**之后**才解码，因此 &lt;100&gt; 不会被误当成标签吃掉。
    assert clean_body("价格 &lt;100&gt; 元").text == "价格 <100> 元"


@pytest.mark.parametrize(
    "raw",
    [
        "订单号 A-2026-09-01 金额 ¥99.50 件数 3",
        "运单 SF1234567890123，9 月 1 日 14:30 未揽收",
        "支付了 1999.00 元，要求退 15%",
    ],
)
def test_never_rewrites_numbers_or_identifiers(raw: str) -> None:
    """清洗只处理标签、空白与整行丢弃，绝不触碰数字与标点。"""
    assert clean_body(raw).text == raw


def test_drops_quoted_reply_lines() -> None:
    raw = "我的快递还没到\n> 您好，已为您催促\n> 请耐心等待"
    assert clean_body(raw).text == "我的快递还没到"


def test_drops_quoted_lines_with_fullwidth_marker() -> None:
    raw = "问题描述\n＞ 引用内容"
    assert clean_body(raw).text == "问题描述"


def test_cuts_signature_tail_after_delimiter() -> None:
    raw = "正文第一行\n第二个问题\n--\n张先生\n13800000000"
    assert clean_body(raw).text == "正文第一行\n第二个问题"


def test_cuts_signature_tail_at_common_greeting() -> None:
    raw = "登录报错验证码无效\n换手机也试过\n\n谢谢\n张三"
    assert clean_body(raw).text == "登录报错验证码无效\n换手机也试过"


def test_keeps_inline_separator_in_first_half() -> None:
    """中部的分隔线不截断，避免误伤正文。"""
    raw = "--\n第一行\n第二行\n第三行\n第四行"
    assert "--" in clean_body(raw).text


def test_dedupes_consecutive_repeated_lines() -> None:
    raw = "请尽快处理\n请尽快处理\n请尽快处理\n还有别的吗"
    assert clean_body(raw).text == "请尽快处理\n还有别的吗"


def test_collapses_horizontal_whitespace_including_fullwidth() -> None:
    assert clean_body("商品\u3000名称   缺货").text == "商品 名称 缺货"


def test_compresses_blank_line_runs() -> None:
    assert clean_body("第一段\n\n\n\n第二段").text == "第一段\n\n第二段"


def test_reports_clean_version() -> None:
    assert clean_body("任意内容").version == CLEAN_VERSION


def test_blank_input_yields_empty_text() -> None:
    assert clean_body("   \n\n  ").text == ""
