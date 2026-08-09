# RocketMQ 事件契约（v1）

主题：`support.domain.events`。每条 Outbox 事件使用如下信封；`eventId` 为 Outbox 主键，消费者的幂等键是 `consumerName + eventId`。

```json
{
  "eventId": 9001,
  "tenantId": 42,
  "eventType": "approval.approved",
  "payload": "{...}"
}
```

消息 Key 固定为 `tenantId:eventId`，Tag 为 `eventType` 的点号替换成下划线，例如 `approval_approved`。消费者恢复事件中的 `tenantId` 到系统身份上下文后才发布本地领域事件，不能信任 payload 内的租户字段。

| eventType | payload 语义 | 处理要求 |
| --- | --- | --- |
| `approval.approved` | 审批版本、动作和业务幂等键 | 写消费账本后执行一次高风险动作 |
| `ticket.sla.first_response` | `tenantId`、`ticketId`、`dueAt` | 重新读取工单，仅 `NEW` 且仍到期才提醒 |
| `ticket.sla.resolution` | `tenantId`、`ticketId`、`dueAt` | 重新读取工单，已解决/关闭不提醒 |

发送失败由 Outbox 指数退避（最多 8 次）；消费失败返回 `RECONSUME_LATER`，RocketMQ 最多重投 8 次后进入对应消费组的 `%DLQ%` 主题。消费者必须能处理至少一次投递和任意顺序的重复事件。
