"""按配置构造模型网关。

真实模式在阶段 3 接入（OpenAI-compatible HTTP 网关）。在此之前，
``MODEL_MODE=real`` 会在装配阶段**直接失败并给出明确指引**，而不是静默回退到 Mock：

见 AGENTS.md §5「真实模式失败时不得自动切换为 Mock」。演示与测试请保持
``MODEL_MODE=mock``。
"""

from __future__ import annotations

from supportflow.model.domain.gateway import ChatModelGateway, ModelMode
from supportflow.model.infrastructure.mock_gateway import MockChatGateway
from supportflow.shared.config import Settings
from supportflow.shared.errors import ServiceUnavailable

REAL_MODE_GUIDANCE = (
    "MODEL_MODE=real 尚未可用：OpenAI-compatible 网关计划在阶段 3 交付。"
    "在此之前请使用 MODEL_MODE=mock；系统不会在真实模式不可用时降级为 Mock。"
)


def available_model_modes() -> frozenset[str]:
    """当前**实际可运行**的模型模式。

    与 ``Settings.model_mode`` 的区别：后者是部署默认值，本函数回答的是「这个构建
    里有哪些网关真的存在」。阶段 2 只有 Mock，因此按次指定的 ``real`` 应被明确拒绝，
    而不是记成 ``real`` 却由 Mock 执行 —— 那会把评测数据标错。
    """
    return frozenset({ModelMode.MOCK.value})


def build_chat_gateway(settings: Settings) -> ChatModelGateway:
    if settings.model_mode == ModelMode.REAL.value:
        raise ServiceUnavailable(REAL_MODE_GUIDANCE)
    return MockChatGateway()
