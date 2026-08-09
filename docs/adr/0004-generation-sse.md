# ADR 0004：生成与 SSE

## 决策

采用“提交消息返回 generationId + 独立 SSE 事件流”；Redis Stream 保存短期事件，MySQL 保存最终事实。

## 替代方案

单一长连接同步生成。

## 后果与回滚

支持断线重连；Redis 不可用时可从 MySQL 查询最终结果。
