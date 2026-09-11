"""日志配置。

刻意保持朴素：单行结构化程度足够定位问题的最小格式，不引入第三方日志库。
**禁止**把口令、会话令牌、模型 API Key 或客户原文写进日志（AGENTS 规范）。
"""

from __future__ import annotations

import logging
import sys

_DEFAULT_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """幂等：重复调用只会重设级别，不会叠加 handler。"""
    resolved = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT))
        root.addHandler(handler)
    root.setLevel(resolved)
