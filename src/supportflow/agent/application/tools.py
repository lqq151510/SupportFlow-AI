"""工具注册表与工具决策解析。

对齐 PLAN.md §4 的工具表：风险等级固定为 ``READ_ONLY`` / ``LOW_RISK`` / ``HIGH_RISK``。
高风险工具（关闭、转派）**永远不能被执行器直接执行** —— 这里只允许登记为「创建审批
请求」的意图，真正落库由 ``approval`` 模块在阶段 3 S4 完成。

身份与当前工单由**服务端注入**，模型只能给出工具名与参数，无法指定任意工单 ID：
参数校验在 ``validate_arguments`` 里完成，模型提供的 ``ticket_id`` 一律被丢弃。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum

from supportflow.model.domain.gateway import ChatMessage, ChatRequest
from supportflow.shared.errors import ModelResponseInvalid

#: 单次运行默认最多调用工具 8 次；超出即转人工，不得静默放宽（PLAN.md §4）。
MAX_TOOL_CALLS = 8

#: 模型只能请求这些参数键；工单归属始终取服务端上下文。
ALLOWED_ARGUMENT_KEYS = frozenset({"query", "reason"})


class ToolRisk(StrEnum):
    READ_ONLY = "READ_ONLY"
    LOW_RISK = "LOW_RISK"
    HIGH_RISK = "HIGH_RISK"


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    risk: ToolRisk
    description: str

    @property
    def requires_approval(self) -> bool:
        """高风险工具只能创建审批请求，不能直接执行。"""
        return self.risk is ToolRisk.HIGH_RISK


TOOL_REGISTRY: dict[str, ToolSpec] = {
    spec.name: spec
    for spec in (
        ToolSpec("search_knowledge", ToolRisk.READ_ONLY, "检索知识库与历史工单"),
        ToolSpec("get_current_ticket", ToolRisk.READ_ONLY, "读取当前工单的清洗文本"),
        ToolSpec("generate_reply", ToolRisk.LOW_RISK, "产出草稿，不发布"),
        ToolSpec("request_close", ToolRisk.HIGH_RISK, "申请关闭工单，仅创建审批请求"),
        ToolSpec("request_transfer", ToolRisk.HIGH_RISK, "申请转派工单，仅创建审批请求"),
    )
}

EXECUTABLE_TOOLS = frozenset(
    name for name, spec in TOOL_REGISTRY.items() if not spec.requires_approval
)

TOOL_DECISION_SYSTEM_PROMPT = (
    "你是电商售后工单处理助手。你可以在生成草稿前请求**只读**工具补充证据。\n"
    f"可选工具：{', '.join(sorted(EXECUTABLE_TOOLS))}。\n"
    "只输出一个 JSON 对象，字段为：\n"
    '{"tool": <上方工具名之一，或 null 表示证据已足够>, "arguments": {"query": "<检索词>"}}\n'
    "不要输出 Markdown 代码块或任何额外说明。\n"
    "\n"
    "判断规则（必须遵守）：\n"
    "1. 已有证据足以回答客户问题时，**必须**返回 {\"tool\": null}，不要为了保险而继续检索；\n"
    "2. **不要重复**提交相同的工具与相同的检索词 —— 同样的调用不会带来任何新信息；\n"
    "3. 现有证据为空或明显不相关时，可以换一个**不同**的检索词再试；\n"
    "4. 工具调用次数有硬上限，达到上限后本次运行会直接转人工，因此不要无谓消耗。"
)


@dataclass(frozen=True, slots=True)
class ToolDecision:
    """``tool`` 为 ``None`` 表示模型认为当前证据已足够，不再请求工具。"""

    tool: str | None
    arguments: dict[str, str]

    def signature(self) -> str:
        """工具 + 参数的稳定指纹，用于识别「原地打转」的重复请求。"""
        return f"{self.tool}:{json.dumps(self.arguments, sort_keys=True, ensure_ascii=False)}"


def build_tool_decision_request(
    *,
    subject: str,
    body_cleaned: str,
    category: str,
    evidence_count: int,
    remaining_calls: int = MAX_TOOL_CALLS,
) -> ChatRequest:
    return ChatRequest(
        messages=(
            ChatMessage(role="system", content=TOOL_DECISION_SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=(
                    f"工单标题：{subject}\n"
                    f"工单正文：\n{body_cleaned}\n"
                    f"已判定分类：{category}\n"
                    f"当前已检索到的证据条数：{evidence_count}\n"
                    f"剩余可调用工具次数：{remaining_calls}（达到上限将转人工）"
                ),
            ),
        ),
        temperature=0.0,
        response_format="json",
    )


def parse_tool_decision(text: str) -> ToolDecision:
    """解析工具决策。

    - ``tool`` 为 ``null`` / 缺省：模型未请求工具，这是合法结果（证据已足够或放弃补充）。
    - 未知工具名或参数越界：**非法参数不重试**，抛 ``ModelResponseInvalid`` 由调用方转人工。
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ModelResponseInvalid("工具决策不是合法 JSON") from exc
    if not isinstance(payload, dict):
        raise ModelResponseInvalid("工具决策不是 JSON 对象")

    raw_tool = payload.get("tool")
    if raw_tool is None:
        return ToolDecision(tool=None, arguments={})
    if not isinstance(raw_tool, str):
        raise ModelResponseInvalid("工具决策的 tool 字段必须是字符串或 null")

    spec = TOOL_REGISTRY.get(raw_tool)
    if spec is None:
        raise ModelResponseInvalid(f"模型请求了未注册的工具：{raw_tool!r}")
    if spec.requires_approval:
        # 高风险工具即便被模型请求，也不进入只读工具循环；审批在 S4 落地。
        raise ModelResponseInvalid(f"高风险工具不能直接执行：{raw_tool!r}")

    return ToolDecision(tool=spec.name, arguments=validate_arguments(payload.get("arguments")))


def validate_arguments(raw: object) -> dict[str, str]:
    """白名单校验模型提供的参数；越界键一律判为非法，不做静默裁剪。"""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ModelResponseInvalid("工具参数必须是 JSON 对象")
    unknown = set(raw) - ALLOWED_ARGUMENT_KEYS
    if unknown:
        raise ModelResponseInvalid(f"工具参数包含不允许的字段：{sorted(unknown)}")
    arguments: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(value, str):
            raise ModelResponseInvalid(f"工具参数 {key} 必须是字符串")
        arguments[key] = value
    return arguments
