"""确定性 Mock 模型网关。

用于无外部依赖的演示与测试：同样的输入永远得到同样的输出。

**刻意不导入业务模块。** 下面的分类代码与 ``ticket`` 模块的分类枚举保持一致，但
适配器只把它们当作不透明的标签串处理 —— 合法性校验由 ``agent`` 侧完成
（见 PLAN.md「非法枚举值视为模型失败，不猜测、不落库」）。二者的集合一致性由
测试交叉断言，而不是靠跨模块导入来保证。
"""

from __future__ import annotations

import json

from supportflow.model.domain.gateway import (
    ChatCompletion,
    ChatModelGateway,
    ChatRequest,
    ChatUsage,
    ModelMode,
)

MOCK_MODEL_NAME = "mock-chat-v1"

# 顺序参与同分时的确定性决策，请勿随意调整。
_HINTS: dict[str, tuple[str, ...]] = {
    "DELIVERY": ("物流", "快递", "发货", "配送", "到货", "签收", "运费", "揽收", "转运"),
    "RETURN_POLICY": ("退货", "退款", "换货", "退换", "无理由", "运费险", "寄回"),
    "PRODUCT_USAGE": ("怎么用", "如何使用", "使用方法", "说明书", "安装", "保修", "保养"),
    "ACCOUNT": ("账号", "登录", "密码", "注册", "验证码", "绑定", "实名"),
    "COMPLAINT": ("投诉", "差评", "态度", "举报", "太差", "欺骗", "敷衍"),
    "OTHER": (),
}
_FALLBACK_LABEL = "OTHER"


def classify_text(text: str) -> tuple[str, float, tuple[str, ...]]:
    """返回 ``(标签, 置信度, 命中的关键词)``。纯函数，便于单测。"""
    scores: dict[str, list[str]] = {label: [] for label in _HINTS}
    for label, hints in _HINTS.items():
        for hint in hints:
            if hint in text:
                scores[label].append(hint)

    best_label = _FALLBACK_LABEL
    best_hits: list[str] = []
    for label, hits in scores.items():
        if len(hits) > len(best_hits):
            best_label, best_hits = label, hits

    if not best_hits:
        return _FALLBACK_LABEL, 0.30, ()
    confidence = min(0.50 + 0.10 * len(best_hits), 0.95)
    return best_label, round(confidence, 2), tuple(best_hits)


class MockChatGateway(ChatModelGateway):
    def __init__(self) -> None:
        self._mode = ModelMode.MOCK

    @property
    def mode(self) -> ModelMode:
        return self._mode

    @property
    def model_name(self) -> str:
        return MOCK_MODEL_NAME

    def complete(self, request: ChatRequest) -> ChatCompletion:
        user_text = "\n".join(
            message.content for message in request.messages if message.role == "user"
        )
        label, confidence, hits = classify_text(user_text)
        rationale = (
            f"命中关键词：{'、'.join(hits)}" if hits else "未命中任何领域关键词，归入兜底分类"
        )
        if request.response_format == "json":
            text = json.dumps(
                {"category": label, "confidence": confidence, "rationale": rationale},
                ensure_ascii=False,
                sort_keys=True,
            )
        else:
            text = f"{label}（置信度 {confidence}）：{rationale}"

        return ChatCompletion(
            text=text,
            model_name=self.model_name,
            mode=self.mode,
            usage=ChatUsage(
                prompt_tokens=len(user_text),
                completion_tokens=len(text),
            ),
        )
