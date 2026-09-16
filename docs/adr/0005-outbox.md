> ⚠️ **已退役 · 旧 Java 架构证据**：本文描述的架构已被 Python 全栈重构替代（ADR-0008，`codex/supportflow-agent-python`）。
> 内容仅作历史证据保留，不代表当前系统；现行基线以仓库根目录的 `PLAN.md` 与 `AGENTS.md` 为准。

# ADR 0005：Outbox 一致性

## 决策

高风险动作和领域事件先与业务数据同事务写 Outbox，再异步投递 RocketMQ。SLA 调度的去重标记与 Outbox 事件也必须原子提交；Outbox 写入失败时回滚标记，让补偿扫描可以安全重试。

## 替代方案

事务后直接发 MQ。

## 后果与回滚

避免数据库成功但消息丢失；消费者按事件 ID 幂等。
