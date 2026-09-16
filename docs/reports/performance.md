> ⚠️ **已退役 · 旧 Java 架构证据**：本文描述的架构已被 Python 全栈重构替代（ADR-0008，`codex/supportflow-agent-python`）。
> 内容仅作历史证据保留，不代表当前系统；现行基线以仓库根目录的 `PLAN.md` 与 `AGENTS.md` 为准。

# 第 8 周性能验收报告

- 执行时间：2026-08-12
- 工具：k6 2.2.0（macOS arm64）
- 应用：本地 Spring Boot、H2、显式启用的确定性 Mock Model
- 自动准备：临时租户、消费者、知识库、索引文档和会话；临时访问令牌在退出时删除

## 普通 API：100 RPS

- 场景：`GET /api/v1/customer/orders`
- 持续时间：30 秒
- 完成请求：3001
- 实际吞吐：100.02 RPS
- P95：3.84 ms（门槛 `< 300 ms`）
- 错误率：0.00%（门槛 `< 1%`）
- 结果：通过

原始报告：[k6-api-orders.json](k6-api-orders.json)

## SSE：100 并发

- 场景：提交消息后连接对应 generation SSE
- 并发：100 VUs
- 持续时间：30 秒
- 完整迭代：3000
- SSE 建连 P95：46.11 ms（门槛 `< 1000 ms`）
- HTTP 错误率：0.00%（门槛 `< 1%`）
- 结果：通过

原始报告：[k6-sse-chat.json](k6-sse-chat.json)

## 复现

```zsh
./perf/run-load-tests.sh
```

该结果用于本地演示基线，不代表公有云、跨地域网络或真实第三方模型的容量上限。真实模型压测必须单独控制供应商限流、成本与数据合规。
