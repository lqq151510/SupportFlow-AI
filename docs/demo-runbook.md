# SupportFlow AI 演示与故障验证手册

## 演示闭环

1. 使用 `POST /api/v1/tenants/register` 创建租户管理员，并用 `POST /api/v1/customers/register` 创建消费者。
2. 消费者登录后创建会话，再以 `Idempotency-Key` 提交消息；接口返回 `202` 和 `generationId`。
3. 使用 `GET /api/v1/customer/generations/{generationId}/events` 读取 SSE。断线后带 `Last-Event-ID` 重连；事件协议见 `docs/contracts/generation-sse.md`。
4. 只有达到当前租户 RAG 的最低分数和最小引用数时才生成回复；否则收到 `knowledge.insufficient` 并创建转人工工单。
5. 坐席通过 `/api/v1/admin/tickets` 领取、评论、解决并关闭工单。SLA 监控只对仍到期的未响应/未解决工单写一次 Outbox 告警。
6. 退款/补偿请求创建审批；批准写入 Outbox，消息消费者以 `consumerName + eventId` 幂等执行。

## 故障验证

| 场景 | 预期结果 | 检查入口 |
| --- | --- | --- |
| 模型 5xx 或协议错误 | `model.failed` 后转人工；不持久化伪造 AI 回复 | SSE、工单列表 |
| 检索无证据或低于门槛 | 不调用模型，写 `knowledge.insufficient` 并转人工 | SSE、工单列表 |
| Outbox 发送失败 | 保持 `PENDING`，指数退避；第 8 次失败转为 `FAILED` | `GET /api/v1/admin/outbox/failed` |
| RocketMQ 消费失败 | 返回 `RECONSUME_LATER`，超过消费重试次数由 broker 投入 `%DLQ%` | RocketMQ 控制台、事件契约 |
| SSE 浏览器断线 | 生成不中断；用最后 SSE id 重放未收到事件 | `Last-Event-ID` 请求 |
| 重复审批/MQ 投递 | 审批、Outbox 与消费账本只产生一次业务效果 | 审批记录、`consumed_events` |

## 可重复验证

```zsh
mvn -B -f backend/pom.xml test
npm --prefix frontend run build
```

在 Docker 阶段再执行 Testcontainers 和完整 k6；它们依赖实际容器运行时与压测工具，不能由 H2/mock 测试替代。
