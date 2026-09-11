"""统一时间源。全部时间戳为 UTC，落库使用带时区的 ``TIMESTAMPTZ``。"""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)
