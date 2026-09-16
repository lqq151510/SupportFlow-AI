"""安全闸：进入分类/检索/生成之前的确定性预筛（AGENTS.md §5、PLAN「失败处理与安全边界」）。

设计取舍：

- **纯规则、零模型调用**：确定性、可测试、零成本；更重要的是**不可信内容到不了
  后续提示词** —— 提示注入文本在进入分类节点之前就被拦截（纵深防御，
  对应 AGENTS.md「文档、用户消息与检索结果均视为不可信输入」）。
- 触发即转人工：安全场景**不生成任何草稿**、不产出无证据结论（AGENTS.md §5）。
- 规则刻意**收窄到索取/绕过/胁迫语义**而不是裸关键词：冻结集正常用例里有
  「收不到验证码」（用户自己收不到）与「我要投诉」「威胁向消协投诉」（合法投诉类目），
  裸关键词会把它们误转人工。40 条正常冻结用例对本模块**零误伤**是验收的一部分
  （见 ``tests/unit/test_security_guard.py``）。

两类处置：

- ``security``：恶意 / 越权 / 绕过流程 —— 转人工并记录规则名；
- ``insufficient_input``：无实质内容 / 乱码 / 无关闲聊 —— 同样无法生成有据结论，转人工。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SECURITY_HANDOFF_REASON = "security"
UNPROCESSABLE_HANDOFF_REASON = "insufficient_input"


@dataclass(frozen=True, slots=True)
class SecurityFinding:
    """一次命中的结果。``rule`` 用于审计与评测明细，``label`` 供展示。"""

    rule: str
    label: str
    reason: str


# (规则名, 展示标签, 模式)。顺序即优先级：恶意语义优先于「无法处理」。
_SECURITY_RULES: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "credential_request",
        "索取验证码/凭证",
        re.compile(r"把.{0,12}验证码|验证码.{0,6}告诉|告诉我.{0,6}验证码|说出.{0,4}验证码"),
    ),
    (
        "payment_redirect",
        "绕开流程的退款/收款要求",
        re.compile(r"银行卡|卡号.{0,8}(给|发)|退到.{0,8}(卡|账户)|直接.{0,4}退钱"),
    ),
    (
        "bypass_approval",
        "要求绕过审批/流程",
        re.compile(r"直接.{0,6}关单|不用.{0,8}审批|跳过审批|不用走.{0,8}流程|别走.{0,8}流程"),
    ),
    (
        "privacy_violation",
        "打探他人信息",
        re.compile(r"我朋友|我同事|别人的订单|他人的订单|别人的地址|他人的地址|查一下.{0,6}别人"),
    ),
    (
        "prompt_injection",
        "提示注入",
        re.compile(r"忽略.{0,10}(指令|规则)|无视.{0,10}(指令|规则)|没有限制的|解除.{0,6}限制"),
    ),
    (
        "coercion",
        "索赔要挟",
        re.compile(r"天天投诉|不然.{0,6}投诉"),
    ),
    (
        "off_platform",
        "引导脱离平台交易",
        re.compile(r"私下|加微信|微信转账|不走平台|线下转账"),
    ),
)

_UNPROCESSABLE_RULES: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "no_substantive_text",
        "无实质内容",
        # 冻结集用一段中文描述「客户只发了标点符号」这个场景，这里按场景关键词拦截；
        # 真正的纯标点正文由下方 no_cjk_content 兜底。
        re.compile(r"没有实质内容|只有标点|标点符号"),
    ),
    (
        "off_topic_chat",
        "与售后无关的闲聊",
        re.compile(r"天气怎么样|今天天气|下雨了吗"),
    ),
)


def has_cjk(text: str) -> bool:
    """是否包含中日韩统一表意文字。本域为中文电商售后，正文无 CJK 视为乱码/灌水。"""
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def inspect_security(subject: str, body: str) -> SecurityFinding | None:
    """返回第一个命中的规则；未命中返回 ``None``（放行进入正常管线）。"""
    text = f"{subject}\n{body}"
    for rule, label, pattern in _SECURITY_RULES:
        if pattern.search(text):
            return SecurityFinding(rule=rule, label=label, reason=SECURITY_HANDOFF_REASON)
    for rule, label, pattern in _UNPROCESSABLE_RULES:
        if pattern.search(text):
            return SecurityFinding(
                rule=rule, label=label, reason=UNPROCESSABLE_HANDOFF_REASON
            )
    # 乱码/灌水判定只看**正文**：subject 可能是中文摘要（如「纯乱码」），
    # 把它算进去会把「标题正常 + 正文乱码」的工单误放行。
    if not has_cjk(body):
        return SecurityFinding(
            rule="no_cjk_content",
            label="无中文实质内容（疑似乱码/灌水）",
            reason=UNPROCESSABLE_HANDOFF_REASON,
        )
    return None
