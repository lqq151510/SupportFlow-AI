"""重试策略单测：只重试瞬时错误，且退避次数精确。"""

from __future__ import annotations

import pytest

from supportflow.agent.application.retry import with_retries
from supportflow.shared.errors import ModelUnavailable


class Boom(Exception):
    """故意不继承 ModelUnavailable，用于验证「非瞬时错误不重试」。"""


def _no_sleep(_: float) -> None:
    return None


def test_returns_first_success_without_retrying() -> None:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    result = with_retries(
        operation,
        attempts=3,
        base_delay_seconds=0.0,
        retry_on=(ModelUnavailable,),
        sleeper=_no_sleep,
    )
    assert result == "ok"
    assert calls == 1


def test_retries_transient_error_then_succeeds() -> None:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ModelUnavailable("上游 503")
        return "recovered"

    delays: list[float] = []
    result = with_retries(
        operation,
        attempts=5,
        base_delay_seconds=0.25,
        retry_on=(ModelUnavailable,),
        sleeper=delays.append,
    )
    assert result == "recovered"
    assert calls == 3
    # 指数退避：0.25 * 2^0, 0.25 * 2^1
    assert delays == [0.25, 0.5]


def test_raises_last_error_after_exhausting_attempts() -> None:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        raise ModelUnavailable("一直失败")

    with pytest.raises(ModelUnavailable):
        with_retries(
            operation,
            attempts=3,
            base_delay_seconds=0.0,
            retry_on=(ModelUnavailable,),
            sleeper=_no_sleep,
        )
    assert calls == 3


def test_does_not_retry_non_transient_error() -> None:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        raise Boom("参数错误")

    with pytest.raises(Boom):
        with_retries(
            operation,
            attempts=4,
            base_delay_seconds=0.0,
            retry_on=(ModelUnavailable,),
            sleeper=_no_sleep,
        )
    assert calls == 1


def test_rejects_invalid_attempts() -> None:
    with pytest.raises(ValueError, match="attempts"):
        with_retries(
            lambda: "x",
            attempts=0,
            base_delay_seconds=0.0,
            retry_on=(ModelUnavailable,),
            sleeper=_no_sleep,
        )
