"""中文全文检索的规范化与确定性 Mock 向量。

PostgreSQL 内建 parser 不负责中文切词。这里先用 jieba 产出空格分隔 token，随后由
``to_tsvector('simple', ...)`` 入库；查询走同一份 token 化规则，GIN 才有真实词级召回。
Mock 向量仅服务阶段 3 S1 的索引和 RRF 验证，真实 Embedding 在 S3 替换并新建索引版本。
"""

from __future__ import annotations

import hashlib
import math
import re

import jieba

TOKEN_RE = re.compile(r"[\u4e00-\u9fff]+|[a-zA-Z0-9][a-zA-Z0-9_-]*")
EMBEDDING_DIMENSION = 64


def tokenize(text: str) -> str:
    normalized = " ".join(text.lower().split())
    terms: list[str] = []
    for fragment in TOKEN_RE.findall(normalized):
        if any("\u4e00" <= char <= "\u9fff" for char in fragment):
            terms.extend(term.strip() for term in jieba.lcut(fragment) if term.strip())
        else:
            terms.append(fragment)
    return " ".join(terms)


def mock_embedding(text: str) -> list[float]:
    """按 token 哈希投影到固定维度，确保离线测试可重复而不会伪称为真实语义向量。"""
    values = [0.0] * EMBEDDING_DIMENSION
    for token in tokenize(text).split():
        digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSION
        values[bucket] += 1.0 if digest[4] & 1 else -1.0
    magnitude = math.sqrt(sum(value * value for value in values))
    return [value / magnitude for value in values] if magnitude else values
