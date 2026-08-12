# RocketMQ 事件契约（v1）

主题：`support-domain-events`。每条 Outbox 事件使用如下信封；`eventId` 为 Outbox 主键，消费者的幂等键是 `consumerName + eventId`。

```json
{
  "schemaVersion": 1,
  "eventId": "9001",
  "tenantId": "42",
  "eventType": "approval.approved",
  "payload": "{...}",
  "occurredAt": "2026-08-12T08:00:00Z"
}
```

信封由 [`schemas/rocketmq-envelope-v1.schema.json`](schemas/rocketmq-envelope-v1.schema.json) 约束。Snowflake ID 必须作为十进制字符串传输，避免 JavaScript 精度损失；消费者只接受 `schemaVersion=1`，未知版本返回失败并进入 RocketMQ 重试/DLQ 流程。

消息 Key 固定为 `tenantId:eventId`，Tag 为 `eventType` 的点号替换成下划线，例如 `approval_approved`。消费者恢复事件中的 `tenantId` 到系统身份上下文后才发布本地领域事件，不能信任 payload 内的租户字段。

| eventType | payload 语义 | 处理要求 |
| --- | --- | --- |
| `approval.approved` | [`approval-approved-v1.schema.json`](schemas/approval-approved-v1.schema.json)：审批版本、执行版本、订单证据和业务幂等键 | 业务执行和结果 Outbox 成功后才写消费账本 |
| `refund.executed` | [`refund-executed-v1.schema.json`](schemas/refund-executed-v1.schema.json)：原审批事件、版本和业务幂等键 | 仅供审计/下游通知，不再次触发退款 |
| `ticket.sla.first_response` | `tenantId`、`ticketId`、`dueAt` | 重新读取工单，仅 `NEW` 且仍到期才提醒 |
| `ticket.sla.resolution` | `tenantId`、`ticketId`、`dueAt` | 重新读取工单，已解决/关闭不提醒 |

SLA 事件在工单创建事务中写入 Outbox；RocketMQ producer 使用 `dueAt` 设置绝对 `deliverTimeMs`，使首次响应和解决提醒在截止时间送达。数据库扫描任务只作为事务回滚或历史数据的补偿，不替代 Broker 延时投递。

发送失败由 Outbox 指数退避（最多 8 次）；消费失败返回 `RECONSUME_LATER`，RocketMQ 最多重投 8 次后进入对应消费组的 `%DLQ%` 主题。消费者必须能处理至少一次投递和任意顺序的重复事件。兼容升级只能新增可选字段；删除字段、改变类型或语义时必须发布新 `schemaVersion` 和新 Schema 文件，并让消费者在显式支持后再切换生产者。
