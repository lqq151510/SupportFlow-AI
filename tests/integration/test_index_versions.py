"""索引版本隔离（真实 PostgreSQL）。

`AGENTS.md` §7：**不得在同一向量列混用不同模型的向量**。落到代码上，最关键的保证是
「检索必须按 ``index_version`` 过滤」—— 少了它，两个模型的向量会被放进同一个余弦
距离里比较，而不同向量空间之间的距离没有意义。

这里直接攻击那条不变量：只在版本 A 下写入向量，然后用版本 B 去搜 —— 必须一条都搜不到。
若过滤被移除，本用例会失败。
"""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from supportflow.knowledge.domain.index_versions import (
    LEGACY_INDEX_VERSION,
    VERSIONED_EMBEDDING_DIMENSION,
    versioned_index_version,
)
from supportflow.knowledge.domain.models import NewKnowledgeChunk, NewKnowledgeDocument
from supportflow.knowledge.infrastructure.repository import SqlAlchemyKnowledgeRepository
from supportflow.shared.db import session_scope

VERSION_A = versioned_index_version("bge-m3-1024-v1", "BAAI/bge-m3")
VERSION_B = versioned_index_version("other-model-1024-v1", "some/other-model")

@pytest.fixture(autouse=True)
def _clean_synthetic_versions(migrated: None) -> Iterator[None]:
    """每个用例前后清掉本模块合成出来的两个索引版本。

    刻意不依赖 conftest 的 TRUNCATE 时机：本模块自己造版本名，自己负责清干净，
    这样无论用例以什么顺序执行、或同一库上重复运行，结论都稳定。
    """
    _reset()
    yield
    _reset()


def _reset() -> None:
    with session_scope() as session:
        session.execute(
            text(
                "DELETE FROM knowledge_documents "
                "WHERE index_version IN (:a, :b)"
            ),
            {"a": VERSION_A.name, "b": VERSION_B.name},
        )


CHUNK_TEXTS = (
    "物流长时间未更新时，先核实运单状态；确认异常后为客户补发并告知新的时效。",
    "退款申请需要转人工确认，不得直接承诺退款金额。",
)


def _vector(seed: int) -> list[float]:
    return [((seed + index) % 17) / 17 for index in range(VERSIONED_EMBEDDING_DIMENSION)]


def _index_document_under(spec_name: str, model: str) -> list[UUID]:
    """在给定索引版本下建一篇文档（含切片与向量），返回切片 id。

    刻意走完整的写入路径：文档、切片、向量三者必须同属**同一个索引版本**，
    因此检索的两条路线才会用同一个判据。
    """
    with session_scope() as session:
        repository = SqlAlchemyKnowledgeRepository(session)
        document_id = repository.add_document(
            NewKnowledgeDocument(
                title=f"doc-{spec_name}",
                mime_type="text/markdown",
                object_key=f"uploads/{uuid4()}.md",
                content_hash=uuid4().hex,
                index_version=spec_name,
                embedding_model=model,
                embedding_dim=VERSIONED_EMBEDDING_DIMENSION,
            )
        )
        chunk_ids = repository.add_chunks(
            document_id,
            [
                NewKnowledgeChunk(
                    chunk_no=index,
                    content=content,
                    tokenized_content="物流 延误 补发 退款 人工",
                    token_count=6,
                    locator=f"chunk-{index}",
                    index_version=spec_name,
                    # 旧列要求 64 维；新版检索不读它，这里只保证写入不违反旧约束。
                    embedding=[0.0] * 64,
                )
                for index, content in enumerate(CHUNK_TEXTS)
            ],
        )
        repository.add_chunk_vectors(
            chunk_ids,
            index_version=spec_name,
            embedding_model=model,
            vectors=[_vector(index) for index in range(len(chunk_ids))],
        )
        repository.mark_document_indexed(document_id)
    return chunk_ids


def test_search_within_the_indexed_version_finds_the_document() -> None:
    _index_document_under(VERSION_A.name, VERSION_A.embedding_model)

    with session_scope() as session:
        results = SqlAlchemyKnowledgeRepository(session).search_versioned(
            query_tokens="物流",
            embedding=_vector(0),
            index_version=VERSION_A.name,
            limit=5,
        )

    assert results, "同一版本内应能检索到结果"
    assert all(item.citation.source_version == VERSION_A.name for item in results)


def test_search_never_returns_vectors_from_another_index_version() -> None:
    """只在版本 A 建索引，用版本 B 搜 —— 必须空。

    这是「不混用不同模型的向量」的直接检验：过滤一旦缺失，版本 B 的查询就会命中
    版本 A 的向量，而两个向量空间之间的距离没有意义。
    """
    _index_document_under(VERSION_A.name, VERSION_A.embedding_model)

    with session_scope() as session:
        results = SqlAlchemyKnowledgeRepository(session).search_versioned(
            query_tokens="物流",
            embedding=_vector(0),
            index_version=VERSION_B.name,
            limit=5,
        )

    assert results == [], "检索串到了别的索引版本"


def test_two_versions_coexist_without_leaking_into_each_other() -> None:
    """两个版本同时存在时，各自只看得见自己。"""
    _index_document_under(VERSION_A.name, VERSION_A.embedding_model)
    _index_document_under(VERSION_B.name, VERSION_B.embedding_model)

    with session_scope() as session:
        repository = SqlAlchemyKnowledgeRepository(session)
        results_a = repository.search_versioned(
            query_tokens="物流", embedding=_vector(0), index_version=VERSION_A.name, limit=10
        )
        results_b = repository.search_versioned(
            query_tokens="物流", embedding=_vector(0), index_version=VERSION_B.name, limit=10
        )

    assert results_a and results_b
    assert {item.citation.source_version for item in results_a} == {VERSION_A.name}
    assert {item.citation.source_version for item in results_b} == {VERSION_B.name}


def test_versioned_search_ignores_the_legacy_mock_index(
    client: object, demo_users: None, indexed_knowledge: None, logged_in_admin: str
) -> None:
    """旧版 Mock 索引（64 维列）对新版检索不可见。

    前置夹具导入的文档属于 ``mock-v1``，只写了旧列。新版索引版本去搜它必须为空 ——
    否则说明新版检索偷偷读了旧列，而旧列存的是**另一个模型**的向量。
    """
    with session_scope() as session:
        results = SqlAlchemyKnowledgeRepository(session).search_versioned(
            query_tokens="物流",
            embedding=_vector(3),
            index_version=VERSION_A.name,
            limit=5,
        )

    assert results == [], "新版检索读到了旧版向量存储"


def test_same_chunk_can_carry_two_versions() -> None:
    """主键 ``(chunk_id, index_version)`` 允许同一切片并存多个版本的向量。

    这是 expand-contract 的前提：重新索引不会破坏旧版本的检索能力。
    """
    chunk_ids = _index_document_under(VERSION_A.name, VERSION_A.embedding_model)
    with session_scope() as session:
        SqlAlchemyKnowledgeRepository(session).add_chunk_vectors(
            chunk_ids,
            index_version=VERSION_B.name,
            embedding_model=VERSION_B.embedding_model,
            vectors=[_vector(index) for index in range(len(chunk_ids))],
        )

    with session_scope() as session:
        stored = session.execute(
            text(
                "SELECT index_version, count(*) FROM knowledge_chunk_vectors "
                "WHERE chunk_id = ANY(:ids) GROUP BY index_version ORDER BY index_version"
            ),
            {"ids": chunk_ids},
        ).all()

    counts = {str(row[0]): int(row[1]) for row in stored}
    assert counts == {VERSION_A.name: len(chunk_ids), VERSION_B.name: len(chunk_ids)}, counts


def test_legacy_index_version_is_mapped_to_the_legacy_route() -> None:
    """路由判定纯由命名契约决定，不查库 —— 检索热路径不该多一次往返。"""
    from supportflow.knowledge.domain.index_versions import LEGACY_ROUTE, route_for

    assert route_for(LEGACY_INDEX_VERSION) == LEGACY_ROUTE
    assert route_for(VERSION_A.name) != LEGACY_ROUTE


@pytest.mark.parametrize("unknown", ["", "mock-v2", "bge-m3-1024"])
def test_unknown_versions_route_to_the_versioned_storage(unknown: str) -> None:
    """非旧版名称一律走新版存储，避免把未知版本误读成旧列。"""
    from supportflow.knowledge.domain.index_versions import LEGACY_ROUTE, route_for

    assert route_for(unknown) != LEGACY_ROUTE
