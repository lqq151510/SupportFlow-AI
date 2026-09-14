"""引用校验单测。

对齐 PLAN.md §3：检索为空、证据不足或引用无法校验时判为失败，不生成无证据结论。
"""

from __future__ import annotations

from typing import Any

from supportflow.agent.application.drafting import (
    MIN_EVIDENCE_SCORE,
    build_draft_request,
    validate_citations,
)


def _evidence(
    *,
    source_id: str = "doc-1",
    chunk_id: str | None = "chunk-1",
    score: float = 2 / 61,
    quote: str = "物流长时间未更新时核实后补发",
) -> dict[str, Any]:
    return {
        "source_type": "KNOWLEDGE",
        "source_id": source_id,
        "source_version": "mock-v1",
        "chunk_id": chunk_id,
        "locator": "chunk:1",
        "quote_text": quote,
        "rank_no": 1,
        "score": score,
        "full_text_rank": 1,
        "vector_rank": 1,
    }


def test_empty_retrieval_is_rejected() -> None:
    check = validate_citations(draft_text="草稿", citations=[], retrieval=[])
    assert check.ok is False
    assert check.reason == "retrieval_empty"


def test_no_citation_is_rejected() -> None:
    check = validate_citations(draft_text="草稿", citations=[], retrieval=[_evidence()])
    assert check.ok is False
    assert check.reason == "no_citation"


def test_score_below_threshold_is_insufficient_evidence() -> None:
    weak = _evidence(score=MIN_EVIDENCE_SCORE / 2)
    check = validate_citations(draft_text="草稿 [1]", citations=[weak], retrieval=[weak])
    assert check.ok is False
    assert check.reason == "insufficient_evidence"


def test_citation_outside_this_run_retrieval_is_rejected() -> None:
    """凭空引用：引用清单里的来源不在本次检索结果中。"""
    foreign = _evidence(source_id="doc-from-another-run", chunk_id="chunk-x")
    check = validate_citations(
        draft_text="草稿 [1]", citations=[foreign], retrieval=[_evidence()]
    )
    assert check.ok is False
    assert check.reason == "citation_not_retrieved"


def test_out_of_range_marker_is_rejected() -> None:
    evidence = _evidence()
    check = validate_citations(
        draft_text="草稿 [1] 以及 [3]", citations=[evidence], retrieval=[evidence]
    )
    assert check.ok is False
    assert check.reason == "citation_out_of_range"
    assert check.invalid_markers == (3,)


def test_valid_draft_passes() -> None:
    evidence = _evidence()
    check = validate_citations(
        draft_text="物流无更新时可核实后补发 [1]", citations=[evidence], retrieval=[evidence]
    )
    assert check.ok is True
    assert check.reason is None


def test_draft_without_markers_is_accepted_when_evidence_is_valid() -> None:
    """结构化引用由服务端从本次检索结果中挑出，正文是否带标记不影响引用可信度。"""
    evidence = _evidence()
    check = validate_citations(draft_text="已为您核实", citations=[evidence], retrieval=[evidence])
    assert check.ok is True


def test_history_ticket_evidence_uses_null_chunk_id() -> None:
    """历史工单没有切片 ID，去重身份退化为 (来源类型, 来源 ID, None)。"""
    history = _evidence(chunk_id=None)
    check = validate_citations(draft_text="草稿 [1]", citations=[history], retrieval=[history])
    assert check.ok is True


def test_draft_request_numbers_evidence_for_the_model() -> None:
    request = build_draft_request(
        subject="快递没到",
        body_cleaned="物流无更新",
        category="DELIVERY",
        evidence=[_evidence(), _evidence(source_id="doc-2", chunk_id="chunk-2")],
    )
    body = request.messages[1].content
    assert "[1]" in body
    assert "[2]" in body


def test_draft_request_handles_empty_evidence() -> None:
    request = build_draft_request(
        subject="快递没到", body_cleaned="物流无更新", category="DELIVERY", evidence=[]
    )
    assert "未检索到任何证据" in request.messages[1].content
