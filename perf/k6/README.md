# SSE 压测

推荐运行项目提供的隔离脚本。它会启动默认关闭的 Mock Model、自动创建临时租户、知识库和消费者会话，随后执行普通 API 与 SSE 两组压测：

```zsh
./perf/run-load-tests.sh
```

结果写入 `docs/reports/k6-api-orders.json` 与 `docs/reports/k6-sse-chat.json`。临时 token 只保存在权限为 `600` 的临时目录中，并在脚本退出时删除。

也可以使用已有的消费者会话手工运行 SSE 场景：

```zsh
SUPPORTFLOW_BASE_URL=http://localhost:8080 \
SUPPORTFLOW_ACCESS_TOKEN='<short-lived-token>' \
SUPPORTFLOW_CONVERSATION_ID=123 \
K6_VUS=100 K6_DURATION=30s \
k6 run perf/k6/sse-chat.js
```

脚本每个虚拟用户以唯一 `Idempotency-Key` 提交一条消息，然后建立其对应生成任务的 SSE 连接。门槛：HTTP 错误率低于 1%，SSE 建连 P95 小于 1 秒。它不把 token 写入日志、仓库或报告；真实模型调用应在压测环境使用 Mock Model 配置。
