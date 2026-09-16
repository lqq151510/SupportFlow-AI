"""集中导入全部 ORM 表模块，使 ``Base.metadata`` 完整。

导入本身即是副作用（把表注册进 ``Base.metadata``），因此这里显式声明
``# noqa: F401``，而不是让 lint 把它当成无用导入优化掉。

用途：Alembic 的 ``target_metadata``、以及测试里的建表/清表辅助。
"""

from __future__ import annotations

from sqlalchemy import MetaData

from supportflow.agent.infrastructure import tables as _agent_tables
from supportflow.approval.infrastructure import tables as _approval_tables
from supportflow.evaluation.infrastructure import tables as _evaluation_tables
from supportflow.identity.infrastructure import tables as _identity_tables
from supportflow.knowledge.infrastructure import tables as _knowledge_tables
from supportflow.model.infrastructure import tables as _model_tables
from supportflow.shared import audit as _audit
from supportflow.shared import idempotency as _idempotency
from supportflow.shared.db import Base
from supportflow.ticket.infrastructure import tables as _ticket_tables

# 显式引用一次，表明这些模块是「为副作用而导入」，不是僵尸导入。
_SIDE_EFFECT_MODULES = (
    _agent_tables,
    _approval_tables,
    _evaluation_tables,
    _identity_tables,
    _knowledge_tables,
    _model_tables,
    _audit,
    _idempotency,
    _ticket_tables,
)


def all_metadata() -> MetaData:
    return Base.metadata


__all__ = ["all_metadata"]
