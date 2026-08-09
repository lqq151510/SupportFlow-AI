# 生成 SSE 契约（v1）

端点：`GET /api/v1/customer/generations/{generationId}/events`，认证为消费者 Bearer Token。服务端只允许读取认证用户所属租户且本人创建的生成任务。

浏览器断线后以最后收到的 SSE `id` 放入 `Last-Event-ID` 请求头；服务从严格更大的事件开始重放。Redis Stream 保留 10 分钟，最终状态、AI 消息、Token 与延迟以 MySQL 为准。

| 事件名 | 数据 | 重放语义 |
| --- | --- | --- |
| `generation.queued` | `{"status":"QUEUED"}` | 至多一次状态标记 |
| `generation.running` | `{"status":"RUNNING"}` | 至多一次状态标记 |
| `text.delta` | `{"text":"…"}` | 可重复接收，客户端按 SSE id 去重并顺序拼接 |
| `knowledge.citations` | `[{"rank":1,"documentId":…,"chunkId":…,"content":"…","score":…}]` | 生成过程中的证据快照 |
| `tool.started` / `tool.arguments.delta` / `tool.completed` / `tool.result` | 工具名称、参数或结果 | 只读工具结果可展示；高风险工具产生审批，不直接执行 |
| `model.failed` | `{"code":"…"}` | 终态前的错误说明 |
| `handoff.required` | `{"status":"HANDOFF_REQUIRED"}` | 至多一次终态标记 |

事件数据必须是 JSON；新增字段保持向后兼容，已发布字段不得改名或改变含义。
