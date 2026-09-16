"""操作申请（审批）与执行账本的领域模型。

对齐 PLAN §5 与 §6：

- 关闭与转派统一创建**操作申请**，保存**不可变的动作参数**与**发起时的工单版本**；
- 默认有效期 **30 分钟**；拒绝、过期或**工单版本变化**时不执行；
- 实际操作与执行账本在**同一数据库事务**完成，重复审批只产生一次业务效果。

领域模型里刻意不含「执行」能力 —— 执行属于用例编排，且必须与账本同事务，
放在领域对象的方法里会诱使调用方绕过事务边界。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

#: PLAN §5：默认有效期 30 分钟。
ACTION_REQUEST_TTL = timedelta(minutes=30)


class ActionType(StrEnum):
    """首版只有关闭与转派，两者**永远**是 HIGH_RISK（AGENTS.md §5）。"""

    CLOSE_TICKET = "CLOSE_TICKET"
    TRANSFER_TICKET = "TRANSFER_TICKET"


class ActionRequestStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

    @property
    def is_terminal(self) -> bool:
        return self is not ActionRequestStatus.PENDING


#: 「已处理」的状态集合，用于条件更新与查询。
DECIDED_STATUSES = tuple(
    status for status in ActionRequestStatus if status is not ActionRequestStatus.PENDING
)


@dataclass(frozen=True, slots=True)
class ActionRequest:
    id: UUID
    ticket_id: UUID
    run_id: UUID
    action_type: ActionType
    parameters: dict[str, object]
    ticket_version: int
    target_assignee_id: UUID | None
    status: ActionRequestStatus
    created_at: datetime
    expires_at: datetime
    decided_at: datetime | None
    decided_by: UUID | None
    version: int

    @property
    def requires_target_assignee(self) -> bool:
        return self.action_type is ActionType.TRANSFER_TICKET

    def is_decidable(self, now: datetime) -> bool:
        """只有「待审批且未过期」才能被处理。"""
        return self.status is ActionRequestStatus.PENDING and now < self.expires_at


@dataclass(frozen=True, slots=True)
class NewActionRequest:
    """待创建的申请。参数一经写入不可变，因此用值对象承载。"""

    ticket_id: UUID
    run_id: UUID
    action_type: ActionType
    parameters: dict[str, object]
    ticket_version: int
    target_assignee_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ActionLedgerEntry:
    """执行账本。**只追加**，没有删除接口（AGENTS.md §7）。"""

    id: UUID
    action_request_id: UUID
    idempotency_key: str
    ticket_id: UUID
    action_type: ActionType
    result: dict[str, object]
    executed_at: datetime


@dataclass(frozen=True, slots=True)
class ActionDecision:
    """审批结果。

    ``executed`` 为 ``False`` 时 ``blocked_reason`` 说明原因 —— 拒绝、过期或版本变化
    都必须能被调用方区分，而不是笼统地报「失败」。
    """

    request: ActionRequest
    executed: bool
    ledger_entry: ActionLedgerEntry | None = None
    blocked_reason: str | None = None
    replayed: bool = field(default=False)
