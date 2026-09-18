# RAG 评测基线

日期：2026-08-12

本地 `mock-curated-v1` 基线使用 50 条电商售后用例：40 条知识检索用例和 10 条安全/边界用例。冻结用例位于 `backend/src/test/resources/knowledge-evaluation.json`；预置结果位于 `backend/src/test/resources/knowledge-evaluation-baseline.json`，由 `KnowledgeEvaluationDatasetTest` 在 CI 中重新计算门禁。

| 指标 | 结果 | 门槛 |
| --- | ---: | ---: |
| Recall@5 | 100%（40/40） | >= 80% |
| 有知识结论的引用覆盖率 | 100%（40/40） | 100% |
| 边界用例转人工率 | 100%（10/10） | 100% |

这是一份**静态策展基线**：测试读取已填写的 Top-5、引用与转人工结果，验证用例和报告门槛的一致性；它本身不发起一次检索、模型生成或安全工作流。因此，不能把表中的 100% 作为当前部署或任意外部 Embedding/Chat 供应商的线上质量。

实际检索运行应使用管理端的评测 API 创建租户范围内的评测用例并运行。该路径会调用同一知识模块检索边界、保存 `knowledge_base_version`、逐用例排名、耗时与失败结果。切换真实模型或知识库版本后必须生成新的运行记录，不能复用本报告；运行报告应同时披露失败样本数和与验收口径一致的 Recall@5。最低 RRF 分数由 `supportflow.knowledge.search.minimum-rrf-score` 配置。
