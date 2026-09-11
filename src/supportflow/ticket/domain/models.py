"""工单分类与状态。

分类对外暴露**稳定的 ASCII 代码**，中文标签仅用于展示 —— 这样标签措辞变化不会
改动已落库的数据，也不会破坏接口契约。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class TicketCategory(StrEnum):
    DELIVERY = "DELIVERY"
    RETURN_POLICY = "RETURN_POLICY"
    PRODUCT_USAGE = "PRODUCT_USAGE"
    ACCOUNT = "ACCOUNT"
    COMPLAINT = "COMPLAINT"
    OTHER = "OTHER"


CATEGORY_LABELS: dict[TicketCategory, str] = {
    TicketCategory.DELIVERY: "配送物流",
    TicketCategory.RETURN_POLICY: "退换货政策",
    TicketCategory.PRODUCT_USAGE: "商品使用",
    TicketCategory.ACCOUNT: "账号问题",
    TicketCategory.COMPLAINT: "投诉建议",
    TicketCategory.OTHER: "其他",
}


class TicketStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


@dataclass(frozen=True, slots=True)
class Ticket:
    id: UUID
    ticket_no: str
    submitter_id: UUID
    subject: str
    body_raw: str
    body_cleaned: str
    clean_version: int
    category: TicketCategory | None
    status: TicketStatus
    assignee_id: UUID | None
    version: int
    created_at: datetime
    closed_at: datetime | None = None

    @property
    def category_label(self) -> str | None:
        return CATEGORY_LABELS[self.category] if self.category else None


@dataclass(frozen=True, slots=True)
class NewTicket:
    submitter_id: UUID
    subject: str
    body_raw: str
    body_cleaned: str
    clean_version: int
