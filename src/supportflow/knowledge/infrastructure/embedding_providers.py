"""确定性的本地嵌入实现（旧版索引版本）。

用于没有配置 Embedding 能力时的一切场景：本地开发、测试、以及演示。
它同时定义了旧版索引版本 ``mock-v1`` —— 64 维、写入 ``knowledge_chunks.embedding``。

**它不是「真实失败的降级」**：只有在部署里根本没有启用 Embedding 配置时才会被使用；
真实模式下网关失败会如实报错，不会回退到这里（AGENTS.md §10）。
"""

from __future__ import annotations

from collections.abc import Sequence

from supportflow.knowledge.application.tokenization import mock_embedding
from supportflow.knowledge.domain.index_versions import (
    LEGACY_INDEX_VERSION_SPEC,
    IndexVersionSpec,
)


class MockEmbeddingProvider:
    """确定性哈希嵌入。相同文本永远得到相同向量，因此测试可断言。"""

    def active_index_version(self) -> IndexVersionSpec:
        return LEGACY_INDEX_VERSION_SPEC

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [mock_embedding(text) for text in texts]
