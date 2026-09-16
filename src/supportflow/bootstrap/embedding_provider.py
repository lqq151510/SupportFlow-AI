"""把 model 模块的 Embedding 能力适配成 knowledge 模块的嵌入端口。

**为什么这个适配器在 ``bootstrap`` 而不是任一业务模块里**：`AGENTS.md` §3 要求
跨模块只能调用对方的 ``application`` 服务，且模块内不得直接引用其他模块的
infrastructure。把「知识域端口 ← 模型网关」这层桥接放进组合根，两个模块互不认识，
依赖方向保持单向：knowledge ← bootstrap → model。

行为规则：

- **没有启用 Embedding 配置** → 用确定性 Mock（旧版索引版本）。这是「未配置」，
  不是「真实失败后的降级」；
- **启用了** → 用真实网关，索引版本名由「模型 + 维度」派生，因此换模型或换维度
  自然产生新的索引版本，旧版本数据保持可读。
"""

from __future__ import annotations

from collections.abc import Sequence

from supportflow.knowledge.domain.index_versions import (
    IndexVersionSpec,
    derive_index_version_name,
    versioned_index_version,
)
from supportflow.knowledge.domain.ports import EmbeddingProviderPort as KnowledgeEmbeddingPort
from supportflow.model.application.service import ModelConfigService
from supportflow.model.infrastructure.openai_embedding_gateway import (
    OpenAICompatibleEmbeddingGateway,
)


class ConfiguredEmbeddingProvider:
    """按已启用的 Embedding 配置产出向量，否则退回确定性 Mock。"""

    def __init__(
        self,
        model_configs: ModelConfigService,
        *,
        fallback: KnowledgeEmbeddingPort,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._model_configs = model_configs
        self._fallback = fallback
        self._timeout = timeout_seconds

    def active_index_version(self) -> IndexVersionSpec:
        resolved = self._model_configs.resolve_embedding_config()
        if resolved is None:
            return self._fallback.active_index_version()
        return versioned_index_version(
            derive_index_version_name(resolved.model_name, resolved.embedding_dim),
            resolved.model_name,
        )

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """批量向量化。

        未配置时走 Mock；配置了就用真实网关**一次性提交整批**，而不是逐条调用 ——
        导入一篇文档通常有多个切片，逐条调用会把网络往返放大成 N 倍。
        网关每次调用后关闭，避免在长驻进程里泄漏连接池。
        """
        if not texts:
            return []
        resolved = self._model_configs.resolve_embedding_config()
        if resolved is None:
            return self._fallback.embed(texts)

        # **刻意不下发 `dimensions`**：声明的维度是**校验目标**，不是请求参数。
        # 实测教训：`BAAI/bge-m3` 不支持该参数，下发会直接得到 HTTP 400；
        # 而连接测试（同样走这个网关但没带该参数）因此能通过，两者请求形状不一致。
        # 支持该参数的提供方（如智谱 embedding-3）会按自身默认维度返回，
        # 若与声明不符，下面的维度校验会如实失败并提示对齐配置。
        with OpenAICompatibleEmbeddingGateway(
            base_url=resolved.base_url,
            api_key=resolved.api_key,
            model_name=resolved.model_name,
            timeout_seconds=resolved.timeout_seconds or self._timeout,
        ) as gateway:
            result = gateway.embed(list(texts))

        if result.dimension != resolved.embedding_dim:
            # 与连接测试同样的判据：维度不符属于配置错误，且此时已经写坏索引版本的风险，
            # 因此直接失败，绝不把不匹配的向量写进库里。
            from supportflow.shared.errors import ModelResponseInvalid

            raise ModelResponseInvalid(
                f"embedding_dim_mismatch: 配置声明 {resolved.embedding_dim} 维，"
                f"模型实际返回 {result.dimension} 维"
            )
        return [list(vector) for vector in result.vectors]
