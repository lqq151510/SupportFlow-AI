"""知识导入在无数据库时也必须保持的确定性规则。"""

from __future__ import annotations

import math

from supportflow.knowledge.application.service import CHUNK_SIZE, _chunk_text
from supportflow.knowledge.application.tokenization import (
    EMBEDDING_DIMENSION,
    mock_embedding,
    tokenize,
)


def test_chinese_tokenization_is_stable_and_keeps_search_terms() -> None:
    tokens = tokenize("退款多久到账？订单 ABC-2026 可以查询。")

    assert "退款" in tokens
    assert "abc-2026" in tokens


def test_mock_embedding_is_deterministic_and_unit_normalized() -> None:
    first = mock_embedding("退款处理进度")
    second = mock_embedding("退款处理进度")

    assert first == second
    assert len(first) == EMBEDDING_DIMENSION
    assert math.isclose(sum(value * value for value in first), 1.0)


def test_long_contiguous_chinese_content_is_chunked_by_token_budget() -> None:
    content = "退款处理进度查询" * 800
    chunks = _chunk_text(content)

    assert len(chunks) > 1
    assert all(len(tokenize(chunk).split()) <= CHUNK_SIZE for chunk in chunks)
