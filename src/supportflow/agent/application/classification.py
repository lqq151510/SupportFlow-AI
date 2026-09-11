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

SYSTEM_PROMPT = (
    "你是电商售后工单分类助手。只能从下列分类代码中选择一个，不得创造新代码：\n"
    + "\n".join(f"- {code}" for code in ALLOWED_CATEGORY_CODES)
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
