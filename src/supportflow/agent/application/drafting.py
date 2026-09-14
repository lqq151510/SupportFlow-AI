"""草稿生成与引用校验。

引用校验是「不生成无证据结论」这一条的实现点，回答两个问题：

1. **证据是否充分** —— 检索非空，且至少一条候选达到证据分数阈值；
2. **引用是否可信** —— 草稿附带的每条结构化引用都必须来自**本次检索结果**，
   正文里若出现 ``[n]`` 形式的引用标记，其序号必须落在本次引用清单范围内。

凭空引用（引用了本次检索里根本不存在的来源）判定失败；失败即转人工，不产出可交付草稿。

分数阈值按 PLAN.md §3「检索门槛在开发集上校准后冻结」——阶段 3 S5 之前该值只是
占位值，语义是「至少有一条候选进入单路 Top 5」。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from supportflow.model.domain.gateway import ChatMessage, ChatRequest

#: 融合后取 Top 5 作为生成依据（PLAN.md §3）。
EVIDENCE_LIMIT = 5

#: RRF 融合分数下限。1/(60+5)：至少有一条候选进入单路 Top 5。
#: S5 冻结开发集校准值之前，这里是占位阈值，语义明确且可测试。
MIN_EVIDENCE_SCORE = 1 / (60 + EVIDENCE_LIMIT)

_MARKER_RE = re.compile(r"\[(\d+)\]")

DRAFT_SYSTEM_PROMPT = (
    "你是电商售后客服助手。基于**提供的证据**撰写给客户的回复草稿。\n"
    "要求：\n"
    "1. 只使用证据中出现的信息，不得补充证据之外的承诺、时效或政策；\n"
    "2. 每条事实后标注对应的证据序号，格式为 [1]、[2]；\n"
    "3. 禁止复述内部来源名称、工单编号或文档标题；\n"
    "4. 证据不足以回答时，直接输出「需要人工确认」，不要编造。"
)


@dataclass(frozen=True, slots=True)
class CitationCheck:
    ok: bool
    reason: str | None = None
    invalid_markers: tuple[int, ...] = ()


def build_draft_request(
    *, subject: str, body_cleaned: str, category: str, evidence: list[dict[str, Any]]
) -> ChatRequest:
    """把检索到的证据编号后交给模型；编号与引用清单的下标一一对应。"""
    lines = [
        f"[{index}] {citation.get('quote_text', '')}"
        for index, citation in enumerate(evidence, start=1)
    ]
    evidence_block = "\n".join(lines) if lines else "（本次未检索到任何证据）"
    return ChatRequest(
        messages=(
            ChatMessage(role="system", content=DRAFT_SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=(
                    f"工单标题：{subject}\n\n工单正文：\n{body_cleaned}\n\n"
                    f"已判定分类：{category}\n\n可用证据：\n{evidence_block}"
                ),
            ),
        ),
        temperature=0.0,
    )


def validate_citations(
    *,
    draft_text: str,
    citations: list[dict[str, Any]],
    retrieval: list[dict[str, Any]],
    min_score: float = MIN_EVIDENCE_SCORE,
) -> CitationCheck:
    """校验草稿证据。

    ``citations`` 是随草稿一并交付的结构化引用（服务端从本次检索结果中挑选），
    ``retrieval`` 是本次检索的完整候选清单 —— 前者必须是后者的子集。
    """
    if not retrieval:
        return CitationCheck(ok=False, reason="retrieval_empty")
    if not citations:
        return CitationCheck(ok=False, reason="no_citation")

    best = max(float(item.get("score") or 0.0) for item in citations)
    if best < min_score:
        return CitationCheck(ok=False, reason="insufficient_evidence")

    known = {_citation_key(item) for item in retrieval}
    if any(_citation_key(item) not in known for item in citations):
        # 凭空引用：引用了本次检索结果里不存在的来源。
        return CitationCheck(ok=False, reason="citation_not_retrieved")

    markers = {int(match) for match in _MARKER_RE.findall(draft_text)}
    invalid = tuple(sorted(number for number in markers if not 1 <= number <= len(citations)))
    if invalid:
        return CitationCheck(ok=False, reason="citation_out_of_range", invalid_markers=invalid)

    return CitationCheck(ok=True)


def _citation_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("source_type")),
        str(item.get("source_id")),
        str(item.get("chunk_id")),
    )
