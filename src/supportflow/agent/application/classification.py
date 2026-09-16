"""分类节点的提示词构造与结构化解析。

按 PLAN.md：「分类由模型输出结构化结果（枚举 + 置信度 + 依据片段），
非法枚举值视为模型失败，不猜测、不落库」。
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from supportflow.model.domain.gateway import ChatMessage, ChatRequest
from supportflow.shared.errors import ModelResponseInvalid
from supportflow.ticket.application.catalog import ALLOWED_CATEGORY_CODES, parse_category
from supportflow.ticket.domain.models import TicketCategory

#: 各分类的边界定义。真实评测（S5，40 条）暴露的错分集中在几处边界：
#: 补发被误判为退换货、保修被误判为退换货、修改收货地址被误判为物流、
#: 要求上门被误判为物流。边界必须写清，而不是指望模型自己猜。
CATEGORY_BOUNDARIES: dict[str, str] = {
    "DELIVERY": (
        "物流与发货的一切问题：快递未到、停滞、签收异常、发货时效、"
        "少件漏发。**补发（货物异常后的重发）属于本类**，不属于退换货。"
    ),
    "RETURN_POLICY": "退货、退款、换货的**流程与政策**咨询（条件、时效、运费分担）。",
    "PRODUCT_USAGE": (
        "商品使用方法、固件与软件问题。**保修、维修、人为损坏的判定"
        "属于本类**，不属于退换货政策。"
    ),
    "ACCOUNT": (
        "账号登录、收货地址与订单信息维护、发票、优惠券等自助服务。"
        "**修改收货地址属于本类**，即使订单已在配送中。"
    ),
    "COMPLAINT": (
        "表达不满、要求赔偿、投诉升级（向消协/监管反映）。"
        "**要求上门等特殊处理诉求也属于本类**。"
    ),
    "OTHER": "与售后无关，或无法归入上述分类。",
}

SYSTEM_PROMPT = (
    "你是电商售后工单分类助手。只能从下列分类代码中选择一个，不得创造新代码：\n"
    + "\n".join(f"- {code}" for code in ALLOWED_CATEGORY_CODES)
    + "\n\n各分类的边界（有重叠时按此判定）：\n"
    + "\n".join(
        f"- {code}：{CATEGORY_BOUNDARIES[code]}"
        for code in ALLOWED_CATEGORY_CODES
        if code in CATEGORY_BOUNDARIES
    )
    + "\n\n只输出一个 JSON 对象，字段为：\n"
    '{"category": "<上方代码之一>", "confidence": <0 到 1 的小数>, '
    '"rationale": "<不超过 50 字的判断依据>"}\n'
    "不要输出 Markdown 代码块或任何额外说明。"
)


@dataclass(frozen=True, slots=True)
class ClassificationOutcome:
    category: TicketCategory
    confidence: float
    rationale: str


def build_request(*, subject: str, body_cleaned: str) -> ChatRequest:
    """构造分类请求。正文使用清洗后的文本，避免把 HTML 噪声喂给模型。"""
    return ChatRequest(
        messages=(
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=f"工单标题：{subject}\n\n工单正文：\n{body_cleaned}",
            ),
        ),
        temperature=0.0,
        response_format="json",
    )


def parse_classification(text: str) -> ClassificationOutcome:
    """解析模型输出。结构或枚举不合法一律抛 ``ModelResponseInvalid``。"""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ModelResponseInvalid("模型输出不是合法 JSON") from exc

    if not isinstance(payload, dict):
        raise ModelResponseInvalid("模型输出不是 JSON 对象")

    raw_category = payload.get("category")
    if not isinstance(raw_category, str):
        raise ModelResponseInvalid("模型输出缺少 category 字段")

    category = parse_category(raw_category)
    if category is None:
        # 不猜测、不取近似值：非法枚举直接判为失败。
        raise ModelResponseInvalid(f"模型返回了未知分类代码：{raw_category!r}")

    confidence_raw = payload.get("confidence", 0.0)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError) as exc:
        raise ModelResponseInvalid("confidence 字段不是数值") from exc
    confidence = min(max(confidence, 0.0), 1.0)

    rationale = payload.get("rationale")
    return ClassificationOutcome(
        category=category,
        confidence=confidence,
        rationale=rationale if isinstance(rationale, str) else "",
    )
