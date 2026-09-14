"""agent 模块的应用层端口。

本模块只声明 agent 需要的能力，不引用其他模块的 Repository 或内部 Service：

- ``TicketGatewayPort`` 由组合根适配 ``ticket`` 仓储实现，只暴露工单事实与「写入分类」
  这一个受控写操作，避免 agent 拿到整个工单仓储；
- ``KnowledgeRetrievalPort`` 由组合根适配 ``KnowledgeService``，只暴露运行内部检索入口。

引用其他模块的**领域类型**（``TicketCategory``）是允许的；禁止的是引用对方的 ORM 模型、
Repository 或内部 Service —— 见 AGENTS.md §3。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from supportflow.identity.domain.models import Principal
from supportflow.ticket.domain.models import Ticket, TicketCategory


class TicketLookupPort(Protocol):
    """``RunService`` 用它做运行可见性判定；由 ``TicketService`` 结构化满足。"""

    def get_ticket(self, principal: Principal, ticket_id: UUID) -> Ticket:
        """返回工单；不存在或无权访问时抛出 ``NotFound``。"""
        ...


@dataclass(frozen=True, slots=True)
class TicketFacts:
    """运行所需的工单只读事实。身份与工单归属由服务端注入，模型无法指定。"""

    ticket_id: UUID
    ticket_no: str
    subject: str
    body_cleaned: str
    clean_version: int
    status: str


class TicketGatewayPort(Protocol):
    def facts(self, ticket_id: UUID) -> TicketFacts | None:
        """返回工单事实；不存在时返回 ``None``。"""
        ...

    def assign_category(self, ticket_id: UUID, category: TicketCategory) -> None:
        """写入分类结果。同一分类重复写入是幂等的。"""
        ...


@dataclass(frozen=True, slots=True)
class Evidence:
    """一条可溯源的检索证据，字段与 ``source_citations`` 表一一对应。"""

    source_type: str
    source_id: str
    source_version: str
    chunk_id: str | None
    locator: str
    quote_text: str
    rank_no: int
    score: float
    full_text_rank: int | None = None
    vector_rank: int | None = None

    def as_state(self) -> dict[str, object]:
        """转为图状态里的纯量字典（LangGraph 会把状态序列化进 JSONB 检查点）。"""
        return {
            "source_type": self.source_type,
            "source_id": self.source_id,
            "source_version": self.source_version,
            "chunk_id": self.chunk_id,
            "locator": self.locator,
            "quote_text": self.quote_text,
            "rank_no": self.rank_no,
            "score": self.score,
            "full_text_rank": self.full_text_rank,
            "vector_rank": self.vector_rank,
        }


class KnowledgeRetrievalPort(Protocol):
    def retrieve_for_run(self, query: str, *, limit: int) -> list[Evidence]:
        """运行内部检索入口。返回按 RRF 融合分数降序的候选证据。"""
        ...
