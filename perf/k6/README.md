# SSE 压测

先通过消费者流程创建一个会话，随后在本机或 CI 中注入短期访问令牌：

```zsh
SUPPORTFLOW_BASE_URL=http://localhost:8080 \
SUPPORTFLOW_ACCESS_TOKEN='<short-lived-token>' \
SUPPORTFLOW_CONVERSATION_ID=123 \
K6_VUS=100 K6_DURATION=30s \
k6 run perf/k6/sse-chat.js
```

脚本每个虚拟用户以唯一 `Idempotency-Key` 提交一条消息，然后建立其对应生成任务的 SSE 连接。门槛：HTTP 错误率低于 1%，SSE 建连 P95 小于 1 秒。它不把 token 写入日志、仓库或报告；真实模型调用应在压测环境使用 Mock Model 配置。
