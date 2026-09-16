"""ticket 接口契约。

约定：

* 主键在 JSON 中一律序列化为**字符串**（UUID）。
* 时间使用 **UTC ISO 8601**，带 ``Z`` 后缀由前端负责本地化。
* 分类只在响应里出现稳定代码 ``category`` 与展示用 ``category_label``；
  请求侧不接受分类（分类由 Agent 判定，不允许客户端指定）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from supportflow.ticket.domain.models import Draft, DraftStatus, Ticket

SUBJECT_MAX_LENGTH = 200
BODY_MAX_LENGTH = 8000
DRAFT_MAX_LENGTH = 8000


class TicketCreateRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=SUBJECT_MAX_LENGTH)
    body: str = Field(min_length=1, max_length=BODY_MAX_LENGTH)
    #: 仅坐席与管理员可用；普通用户传入会被拒绝（403 model_mode_not_permitted）。
    model_mode: str | None = Field(default=None, pattern="^(mock|real)$")


class TicketSubmittedOut(BaseModel):
    """提交工单返回 202：工单已落库，首次运行已入队但**尚未执行**。"""

    ticket_id: str
    ticket_no: str
    run_id: str
    status: str
    model_mode: str


class TicketOut(BaseModel):
    id: str
    ticket_no: str
    subject: str
    category: str | None
    category_label: str | None
    status: str
    assignee_id: str | None
    created_at: datetime
    closed_at: datetime | None

    @classmethod
    def of(cls, ticket: Ticket) -> TicketOut:
        return cls(
            id=str(ticket.id),
            ticket_no=ticket.ticket_no,
            subject=ticket.subject,
            category=ticket.category.value if ticket.category else None,
            category_label=ticket.category_label,
            status=ticket.status.value,
            assignee_id=str(ticket.assignee_id) if ticket.assignee_id else None,
            created_at=ticket.created_at,
            closed_at=ticket.closed_at,
        )


class TicketDetailOut(TicketOut):
    """详情额外返回清洗后的正文、乐观锁版本号，以及草稿链与已发布回复。

    只返回 ``body_cleaned``：原始正文仅用于留档与审计，不通过接口外泄
    （其中可能混有用户误粘贴的敏感内容）。草稿里的 ``citations`` 是服务端从**本次
    检索结果**快照下来的可溯源引用，前端不得伪造来源。
    """

    body_cleaned: str
    clean_version: int
    version: int
    drafts: list[DraftDetailOut]
    published_reply: str | None

    @classmethod
    def with_drafts(cls, ticket: Ticket, drafts: list[Draft]) -> TicketDetailOut:
        base = TicketOut.of(ticket)
        published = next((d for d in drafts if d.status is DraftStatus.PUBLISHED), None)
        return cls(
            **base.model_dump(),
            body_cleaned=ticket.body_cleaned,
            clean_version=ticket.clean_version,
            version=ticket.version,
            drafts=[DraftDetailOut.of(d) for d in drafts],
            published_reply=published.content if published else None,
        )


class DraftDetailOut(BaseModel):
    """一条草稿版本。``citations`` 是结构化引用快照（来源/编号/原文）。"""

    id: str
    ticket_id: str
    version: int
    author: str
    content: str
    citations: list[dict[str, Any]]
    status: str
    editor_user_id: str | None
    run_id: str | None
    created_at: datetime
    published_at: datetime | None
    published_by: str | None

    @classmethod
    def of(cls, draft: Draft) -> DraftDetailOut:
        return cls(
            id=str(draft.id),
            ticket_id=str(draft.ticket_id),
            version=draft.version,
            author=draft.author.value,
            content=draft.content,
            citations=draft.citations,
            status=draft.status.value,
            editor_user_id=str(draft.editor_user_id) if draft.editor_user_id else None,
            run_id=str(draft.run_id) if draft.run_id else None,
            created_at=draft.created_at,
            published_at=draft.published_at,
            published_by=str(draft.published_by) if draft.published_by else None,
        )


class DraftEditRequest(BaseModel):
    content: str = Field(min_length=1, max_length=DRAFT_MAX_LENGTH)


class TicketPageOut(BaseModel):
    items: list[TicketOut]
    total: int
    limit: int
    offset: int
