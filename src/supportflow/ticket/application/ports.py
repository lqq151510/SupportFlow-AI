"""工单模块的应用层端口。

放在 ``application`` 而非 ``domain``，是因为这些端口描述的是**用例协作契约**
（谁在什么时机被调用），而不是业务规则本身。

注意 ``FirstRunSchedulerPort`` 的签名里没有 ``Session``：实现方由容器用同一个
请求级 Session 构造，因此「创建工单」与「创建首次运行」天然处于同一事务，
无需把事务句柄穿过模块边界。

``IdempotencyPort`` 的规范定义在 ``supportflow.shared.idempotency``（跨模块关注点），
这里只做转出，避免各模块各自声明一份同名协议而逐渐漂移。
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from supportflow.shared.idempotency import IdempotencyPort, ReplayedResponse

__all__ = ["FirstRunSchedulerPort", "IdempotencyPort", "ReplayedResponse"]


class FirstRunSchedulerPort(Protocol):
    def schedule_first_run(self, *, ticket_id: UUID, model_mode: str) -> UUID:
        """为新工单创建首次运行，返回 ``run_id``。必须与调用方共享同一事务。"""
        ...
