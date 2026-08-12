# RAG 评测基线

日期：2026-08-12

本地 `mock-curated-v1` 基线使用 50 条电商售后用例：40 条知识检索用例和 10 条安全/边界用例。冻结结果位于 `backend/src/test/resources/knowledge-evaluation-baseline.json`，由 `KnowledgeEvaluationDatasetTest` 在 CI 中重新计算门禁。

| 指标 | 结果 | 门槛 |
| --- | ---: | ---: |
| Recall@5 | 100%（40/40） | >= 80% |
| 有知识结论的引用覆盖率 | 100%（40/40） | 100% |
| 边界用例转人工率 | 100%（10/10） | 100% |

该结果证明本地策展语料与 Mock Model 的可重复交付基线，不代表任意外部 Embedding/Chat 供应商的线上质量。切换真实模型或知识库版本后必须生成新的评测结果，不能复用本报告。检索审计会持久化 `knowledge_base_version`，最低 RRF 分数由 `supportflow.knowledge.search.minimum-rrf-score` 配置。
