"""分类目录：工单分类词表的对外读接口。

其他模块（如 ``agent`` 的分类节点）需要分类代码时从这里取，而不是直达
``ticket.domain``。这样词表变化的出口只有一个，也便于在评审时定位耦合点。
"""

from __future__ import annotations

from supportflow.ticket.domain.models import CATEGORY_LABELS, TicketCategory

ALLOWED_CATEGORY_CODES: tuple[str, ...] = tuple(category.value for category in TicketCategory)


def parse_category(code: str) -> TicketCategory | None:
    """把模型输出的代码解析为枚举。无法识别时返回 ``None``，由调用方判为模型失败。"""
    normalized = code.strip().upper()
    for category in TicketCategory:
        if category.value == normalized:
            return category
    return None


def label_of(category: TicketCategory) -> str:
    return CATEGORY_LABELS[category]
