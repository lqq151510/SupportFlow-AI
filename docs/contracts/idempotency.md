# 写操作幂等契约（v1）

所有产生业务副作用的接口使用 `Idempotency-Key` 请求头。其存储作用域固定为：`tenantId + actorId + operation + key`；匿名注册接口以请求归属的 tenant code 与 email 作为过渡作用域。

| 场景 | operation | 重复相同请求 | 相同 key、不同请求体 | 并发处理中 |
| --- | --- | --- | --- | --- |
| 发送消息 | `conversation.message.create` | 返回首次 `202 + generationId` | 409 `IDEMPOTENCY_KEY_REUSED` | 409 `REQUEST_IN_PROGRESS` |
| 领取工单 | `ticket.claim` | 返回首次结果 | 409 `IDEMPOTENCY_KEY_REUSED` | 409 `REQUEST_IN_PROGRESS` |
| 审批动作 | `approval.decide` | 返回首次结果 | 409 `IDEMPOTENCY_KEY_REUSED` | 409 `REQUEST_IN_PROGRESS` |
| 执行退款 | `refund.execute` | 返回首次结果 | 409 `IDEMPOTENCY_KEY_REUSED` | 409 `REQUEST_IN_PROGRESS` |

存储记录应保存请求体 SHA-256、状态（`PROCESSING`、`COMPLETED`、`FAILED`）、响应状态与响应体，并设定可配置有效期。失败是否可重试由 operation 决定；高风险操作不得因客户端重试产生第二次业务效果。
