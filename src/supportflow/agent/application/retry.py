"""瞬时错误的重试策略。

只重试**瞬时**错误（超时、限流、上游 5xx 映射来的 ``ModelUnavailable``）。
参数错误、权限错误与结构性错误一律不重试 —— 见 PLAN.md「参数错误和权限错误不重试，
持续失败进入人工处理」。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)


def with_retries[T](
    operation: Callable[[], T],
    *,
    attempts: int,
    base_delay_seconds: float,
    retry_on: tuple[type[BaseException], ...],
    sleeper: Callable[[float], None] = time.sleep,
    label: str = "operation",
) -> T:
    """执行 ``operation``，失败时按指数退避重试至多 ``attempts`` 次。

    最后一次失败会原样抛出，由调用方决定转人工还是标记失败。
    """
    if attempts < 1:
        raise ValueError("attempts 必须 >= 1")

    last_error: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except retry_on as exc:
            last_error = exc
            if attempt >= attempts:
                break
            delay = base_delay_seconds * (2 ** (attempt - 1))
            logger.warning(
                "%s 第 %d/%d 次尝试失败，%.2fs 后重试",
                label,
                attempt,
                attempts,
                delay,
                extra={"error": type(exc).__name__},
            )
            sleeper(delay)

    assert last_error is not None  # 循环必然至少抛出一次
    raise last_error
