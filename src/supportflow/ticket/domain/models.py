"""工单分类与状态。

分类对外暴露**稳定的 ASCII 代码**，中文标签仅用于展示 —— 这样标签措辞变化不会
改动已落库的数据，也不会破坏接口契约。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
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


class DraftStatus(StrEnum):
    """草稿版本的生命周期状态。

    ACTIVE 表示当前可编辑/可发布的工作草稿；编辑会派生出新版本并把旧版本置为
    ARCHIVED；发布把 ACTIVE 置为 PUBLISHED（终态，成为给客户的正式回复）。
    """

    ACTIVE = "ACTIVE"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class DraftAuthor(StrEnum):
    """草稿版本的来源：agent 自动生成，或 human 在审核中编辑。"""

    AGENT = "agent"
    HUMAN = "human"


@dataclass(frozen=True, slots=True)
class Draft:
    id: UUID
    ticket_id: UUID
    version: int
    author: DraftAuthor
    content: str
    citations: list[dict[str, Any]]
    status: DraftStatus
    editor_user_id: UUID | None
    run_id: UUID | None
    created_at: datetime
    published_at: datetime | None = None
    published_by: UUID | None = None


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
