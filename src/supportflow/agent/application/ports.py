"""agent 模块的应用层端口。

``TicketLookupPort`` 由 ``ticket`` 模块的 ``TicketService`` 结构化满足 —— 容器直接
把同一个请求级实例传进来，因此不引入新的适配层，也不会产生循环依赖。

引用其他模块的**领域类型**（``Ticket``、``Principal``）是允许的；禁止的是引用
对方的 ORM 模型、Repository 或内部 Service —— 见 AGENTS.md §3。
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from supportflow.identity.domain.models import Principal
from supportflow.ticket.domain.models import Ticket


class TicketLookupPort(Protocol):
    def get_ticket(self, principal: Principal, ticket_id: UUID) -> Ticket:
        """返回工单；不存在或无权访问时抛出 ``NotFound``。"""
        ...
