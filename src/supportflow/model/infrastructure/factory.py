"""按运行模式解析模型网关。

两条规则（AGENTS.md §5、§10）：

1. **真实模式失败不降级为 Mock。** 需要真实网关却没有可用配置时直接失败并给出指引，
   而不是悄悄用 Mock 执行 —— 否则运行会被标记为 ``real`` 却由 Mock 产出，评测数据即失真。
2. **网关按「运行的模式」解析，而不是按部署默认值。** 运行可以按次指定 ``model_mode``；
   若执行时仍沿用装配期的那个网关，就会出现「标记 real、实由 Mock 产出」的失真。
"""

from __future__ import annotations

from collections.abc import Callable

from supportflow.model.domain.gateway import ChatModelGateway, ModelMode
from supportflow.model.domain.models import ResolvedChatConfig
from supportflow.model.infrastructure.mock_gateway import MockChatGateway
from supportflow.model.infrastructure.openai_gateway import OpenAICompatibleChatGateway
from supportflow.shared.errors import ModelConfigInvalid

REAL_MODE_GUIDANCE = (
    "真实模式需要先在「模型配置」里创建一个聊天配置并启用，"
    "同时配置 MODEL_SECRET_MASTER_KEY。系统不会在真实模式不可用时降级为 Mock。"
)

#: 网关解析器：入参是**运行**的模式（``None`` 表示沿用部署默认值）。
GatewayResolver = Callable[[str | None], ChatModelGateway]


def available_model_modes(*, chat_configured: bool) -> frozenset[str]:
    """当前**实际可运行**的模型模式。

    ``real`` 只有在存在已启用且密钥可用的聊天配置时才列入 —— 这样
    ``POST /tickets/{id}/runs {"model_mode":"real"}`` 会在**创建运行时**就得到
    ``409 model_mode_unavailable``，而不是入队一个注定失败的运行。
    """
    modes = {ModelMode.MOCK.value}
    if chat_configured:
        modes.add(ModelMode.REAL.value)
    return frozenset(modes)


def build_chat_gateway(
    mode: str, *, chat_config: ResolvedChatConfig | None = None
) -> ChatModelGateway:
    """按**显式模式**构造网关。

    ``chat_config`` 由调用方通过 ``ModelConfigService.resolve_chat_config()`` 取得；
    Mock 模式**不会**触碰密文，因此未配置主密钥也不影响本地开发与测试。
    """
    if mode != ModelMode.REAL.value:
        return MockChatGateway()
    if chat_config is None:
        raise ModelConfigInvalid(REAL_MODE_GUIDANCE)
    return OpenAICompatibleChatGateway(
        base_url=chat_config.base_url,
        api_key=chat_config.api_key,
        model_name=chat_config.model_name,
        timeout_seconds=chat_config.timeout_seconds,
    )


def build_gateway_resolver(
    *,
    default_mode: str,
    resolve_chat_config: Callable[[], ResolvedChatConfig | None],
) -> GatewayResolver:
    """构造「运行模式 → 网关」的解析器。

    ``resolve_chat_config`` 只在真的需要真实网关时调用，因此 Mock 模式不会解密密钥。
    """

    def resolve(model_mode: str | None) -> ChatModelGateway:
        effective = model_mode or default_mode
        chat_config = resolve_chat_config() if effective == ModelMode.REAL.value else None
        return build_chat_gateway(effective, chat_config=chat_config)

    return resolve
