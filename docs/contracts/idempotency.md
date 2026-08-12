# 写操作幂等契约（v1）

所有产生业务副作用的接口使用 `Idempotency-Key` 请求头。其存储作用域固定为：`tenantId + actorId + operation + key`；匿名注册接口以请求归属的 tenant code 与 email 作为过渡作用域。

优先闭环覆盖发消息、领取工单、审批和退款执行。消息以 `conversation_messages` 的唯一键和原始正文校验重放；工单把领取 key 与领取人写入工单；审批保存决策与审批版本；退款执行保存业务幂等键与执行版本。其他写接口在接入统一持久化拦截器前，不得宣称支持安全重放。

| 场景 | operation | 重复相同请求 | 相同 key、不同请求体 | 并发提交 |
| --- | --- | --- | --- | --- |
| 发送消息 | `conversation.message.create` | 返回首次 `202 + generationId`，不重复发布生成/转人工事件 | 409 `RESOURCE_CONFLICT` | 数据库唯一约束保证只产生一条用户消息 |
| 领取工单 | `ticket.claim` | 返回首次结果 | 409 `RESOURCE_CONFLICT` | 乐观锁失败后按 key 重读；同 key 返回首次结果，其他 key 409 |
| 审批动作 | `approval.decide` | 返回首次结果 | 409 `RESOURCE_CONFLICT` | 审批版本乐观锁只允许一个决策成功 |
| 执行退款 | `refund.execute` | 业务幂等键重复时不产生第二条执行记录 | 事件版本或业务键不一致时拒绝 | 数据库唯一约束 + 消费成功后写台账 |

高风险操作不得因客户端重试、MQ 重投或消费者重启产生第二次业务效果。未来扩展到其余写接口时，统一记录需保存请求体 SHA-256、状态（`PROCESSING`、`COMPLETED`、`FAILED`）、响应状态/响应体与可配置有效期；在该基础设施落地前，接口文档必须逐项标识真实覆盖范围。
