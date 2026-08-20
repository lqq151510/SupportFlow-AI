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
SUPPORTFLOW_JWT_SECRET_BASE64='<at-least-32-byte-base64-secret>' docker compose --profile app config --quiet
```

容器集成测试会分别启动隔离的 MySQL、Redis、Elasticsearch 和 RocketMQ，验证 SQL 连通性、Redis Stream 隔离、真实检索与真实消息生产消费：

```zsh
docker info
mvn -B -f backend/pom.xml \
  -Dtest=InfrastructureContainerIntegrationTest,ElasticsearchContainerIntegrationTest,RocketMqContainerIntegrationTest test
```

`@Testcontainers(disabledWithoutDocker = true)` 只用于开发者不具备 Docker 时避免测试框架初始化失败，不能作为第 8 周容器验收的通过依据。交付脚本和 CI 均先执行 `docker info`；该命令失败时应修复 Docker daemon，而不是接受被跳过的测试。

完整 Compose 已启动时，执行 `./scripts/verify-compose-runtime.sh` 验证后端 `UP`、前端 HTTP 200、Elasticsearch `green`、Redis `PONG` 与 RocketMQ Topic 路由。脚本只读检查，适合在演示前或故障恢复后重复执行。

可恢复的基础设施故障演练必须显式确认目标服务。例如验证 Redis 中断并自动恢复：

```zsh
SUPPORTFLOW_CONFIRM_FAULT_DRILL=yes ./scripts/fault-drill.sh redis
```

脚本只接受 `redis`、`elasticsearch` 和 `rocketmq-broker`，退出时会恢复被停止的服务。演练期间观察 SSE 降级、检索失败转人工或 Outbox 保持待投递，禁止在共享/生产环境运行。

完整 k6 执行方式见 `perf/k6/README.md`；最新实测结果见 `docs/reports/performance.md`。H2 或 HTTP mock 不能替代真实容器验收。
