"""模型接入的唯一领域边界。

业务模块**不得**直接调用 OpenAI 或任何模型 SDK —— 见 AGENTS.md §5。

网关本身只知道「消息进、文本出」，不包含工单分类等业务语义：分类提示词与
结构化解析属于 ``agent`` 模块的职责。这样替换模型实现不必触碰业务规则。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Protocol


class ModelMode(StrEnum):
    MOCK = "mock"
    REAL = "real"


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True, slots=True)
class ChatRequest:
    messages: Sequence[ChatMessage]
    temperature: float = 0.0
    response_format: Literal["text", "json"] = "text"


@dataclass(frozen=True, slots=True)
class ChatUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass(frozen=True, slots=True)
class ChatCompletion:
    text: str
    model_name: str
    mode: ModelMode
    usage: ChatUsage


class ChatModelGateway(Protocol):
    """唯一模型接入点。实现必须显式声明超时与重试次数。"""

    @property
    def mode(self) -> ModelMode: ...

    @property
    def model_name(self) -> str: ...

    def complete(self, request: ChatRequest) -> ChatCompletion: ...
