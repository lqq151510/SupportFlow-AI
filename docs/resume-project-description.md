# SupportFlow AI 简历项目描述

## 一句话介绍

SupportFlow AI 是面向电商售后的多租户全栈 AI 客服平台，覆盖消费者咨询、RAG 检索、SSE 流式回复、人工转接、工单 SLA、高风险审批和可靠消息执行闭环。

## 简历精简版

**SupportFlow AI｜全栈 AI 客服与工单协同平台**

技术栈：Java 21、Spring Boot、Spring Modulith、MyBatis-Plus、MySQL、Redis、Elasticsearch、RocketMQ、React、TypeScript、Docker、Playwright、k6

- 使用 Spring Modulith 与 Clean Architecture 构建模块化单体，按认证上下文统一派生 `tenantId`，并在 MySQL、Redis、Elasticsearch 和消息事件中实现多租户隔离。
- 实现 OpenAI-compatible / Anthropic 双模型协议、RAG 混合检索与 SSE 断线续传；证据不足或模型失败时自动转人工，不生成无依据回复。
- 通过事务 Outbox、RocketMQ 重试/DLQ、消费账本和业务幂等键保证审批后退款/补偿动作可靠且不重复执行。
- 完成消费者与坐席 React 工作台、Playwright 端到端流程、Testcontainers 基础设施测试和 k6 性能门禁；后端 JaCoCo 行/分支覆盖率达到计划阈值。

## 面试展开要点

1. **为什么是模块化单体**：MVP 阶段优先保证事务一致性与交付速度，通过 Modulith 边界测试保留未来拆分能力。
2. **为什么浏览器看到的 ID 是字符串**：MyBatis-Plus Snowflake ID 超过 JavaScript 安全整数范围，API 统一按字符串传输，避免精度丢失导致误判跨租户。
3. **如何保证 AI 不越权**：工具按风险分级；退款和补偿只生成审批请求，批准后由 Outbox 与消费者异步执行，模型不能直接调用真实动作。
4. **如何处理流式可靠性**：Redis Stream 保存短期增量事件，MySQL 保存最终事实，客户端用 `Last-Event-ID` 重放未接收事件。
5. **如何验证质量**：单元/架构/容器/E2E/性能分层测试；普通 API 在 100 RPS 下验证 P95，Mock Model 场景验证 100 个并发 SSE 会话。

所有数字以 [测试报告](reports/testing.md) 和 [性能报告](reports/performance.md) 的最终实测结果为准。
