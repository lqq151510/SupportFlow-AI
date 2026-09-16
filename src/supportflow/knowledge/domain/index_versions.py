"""索引版本：把「向量属于哪个模型、多少维」变成显式契约。

`AGENTS.md` §7 要求索引或 Embedding 模型变更必须创建**新的索引版本**，且
**不得在同一向量列混用不同模型的向量**。PostgreSQL 的 ``vector`` 列维度固定，
因此「维度」不只是元数据，它是**物理存储的一部分** —— 这正是本模块存在的原因：

- 旧版（``mock-v1``）：64 维，向量存在 ``knowledge_chunks.embedding`` 的旧列里；
- 新版（``bge-m3:1024``）：1024 维，向量存在 ``knowledge_chunk_vectors`` 专用表里，
  该表的列维度只服务这一个索引版本。

两个存储**并存**（expand-contract），检索按「当前启用的索引版本」选择路线，
因此绝不会把两个模型的向量放在一起比较。将来换一个不同维度的模型时，
要么新建一张同形状的表，要么出一版改维度的迁移 —— 无论哪种，都是一次**显式决定**。
"""

from __future__ import annotations

from dataclasses import dataclass

#: 旧版（Mock）索引版本：64 维，沿用 ``knowledge_chunks.embedding``。
LEGACY_INDEX_VERSION = "mock-v1"
LEGACY_EMBEDDING_MODEL = "mock-hash-64"
LEGACY_EMBEDDING_DIMENSION = 64

#: 新版专用向量表的列维度。**这是 schema 契约**，改动需要新迁移。
#: 取 1024 的依据：``BAAI/bge-m3`` 原生输出 1024 维（已用真实密钥实测确认）。
VERSIONED_EMBEDDING_DIMENSION = 1024

#: 存向量时使用的表路由。检索据此选择 SQL 分支。
LEGACY_ROUTE = "legacy"
VERSIONED_ROUTE = "versioned"


@dataclass(frozen=True, slots=True)
class IndexVersionSpec:
    """一个索引版本的完整身份：名称、嵌入模型、维度、存储路线。"""

    name: str
    embedding_model: str
    dimension: int
    route: str

    @property
    def is_legacy(self) -> bool:
        return self.route == LEGACY_ROUTE


LEGACY_INDEX_VERSION_SPEC = IndexVersionSpec(
    name=LEGACY_INDEX_VERSION,
    embedding_model=LEGACY_EMBEDDING_MODEL,
    dimension=LEGACY_EMBEDDING_DIMENSION,
    route=LEGACY_ROUTE,
)


def versioned_index_version(name: str, embedding_model: str) -> IndexVersionSpec:
    """由名称与模型构造新版索引版本规格。

    名称建议形如 ``bge-m3-1024-v1``：把维度写进名字，使「换维度 = 换版本」一眼可见。
    维度固定为 :data:`VERSIONED_EMBEDDING_DIMENSION`，因为专用表的列维度就是它 ——
    模型实际维度与此不符时应在**配置阶段**被连接测试拦下，而不是走到这里。
    """
    return IndexVersionSpec(
        name=name,
        embedding_model=embedding_model,
        dimension=VERSIONED_EMBEDDING_DIMENSION,
        route=VERSIONED_ROUTE,
    )


def derive_index_version_name(embedding_model: str, dimension: int) -> str:
    """由模型与维度派生索引版本名。

    把维度写进名字，使「换维度 = 换版本」一眼可见：``BAAI/bge-m3`` + 1024
    → ``bge-m3-1024-v1``。名字是**契约**（存进数据库、出现在引用的 ``source_version``
    里），因此派生规则必须稳定且只依赖模型名与维度。
    """
    slug = embedding_model.rsplit("/", 1)[-1].strip().lower().replace("_", "-")
    return f"{slug}-{dimension}-v1"


def route_for(index_version: str) -> str:
    """按名称判定存储路线。

    刻意**不查库**：路线由版本命名契约决定，写成查库会在检索热路径上多一次往返，
    而且会让「旧版数据是否还在」这种可选项影响主线逻辑。
    """
    if index_version == LEGACY_INDEX_VERSION:
        return LEGACY_ROUTE
    return VERSIONED_ROUTE
