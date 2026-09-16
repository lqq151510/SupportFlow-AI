# Python API 契约（v1 · 现行）

> **状态：现行。** 本文件描述 Python 重构版（FastAPI + LangGraph + PostgreSQL/pgvector）的
> 对外契约。目录中其余文件（`authentication.md`、`generation-sse.md`、`idempotency.md`、
> `rocketmq-events.md`、`schemas/`）描述的是**已退役的 Java 架构**，按 AGENTS.md §11
> 在阶段 5 统一退役；与其冲突之处一律以本文件与 `PLAN.md` 为准。

统一约定（适用于本文件全部端点）：

- 前缀 `API_PREFIX = /api/v1`；认证为**服务端会话**（HttpOnly Cookie，服务端只存令牌哈希），
  写请求必须携带 CSRF 令牌（`X-CSRF-Token`），失败返回 `403 csrf_failed`。
- 错误统一 RFC 9457 `ProblemDetail`，含稳定 `code` 与 `request_id`；
  上游模型的原始诊断信息**只出现在管理员专用路径**（如连接测试），不进入普通错误响应。
- 主键在 JSON 中序列化为字符串；时间使用 UTC ISO 8601。
- **Mock 与真实模式的结果在接口层面可区分**（模型配置的能力字段、评测运行的 `mode`、
  运行记录的 `model_mode` / `chat_model_name`），前端据此分别展示。

## 1. 模型配置 `/api/v1/model-configs`（仅管理员）

聊天与 Embedding 能力分别配置；**API Key 只存 AES-GCM 密文，任何查询接口都不返回**，
响应模型里根本没有密钥字段（类型层面排除，而非序列化时剔除）。

| 接口 | 方法 | 说明 | 成功结果 |
| --- | --- | --- | --- |
| `/model-configs` | GET | 列出配置（含「是否已配置密钥」布尔） | 200 |
| `/model-configs` | POST | 创建；`capability` 为 `CHAT` / `EMBEDDING`（Embedding 必须带 `embedding_dim`） | 201 |
| `/model-configs/{id}` | PATCH | 更新（可只改密钥） | 200 |
| `/model-configs/{id}/enable` | POST | 启用；同类能力其他配置在同一事务内停用（`(capability) WHERE enabled` 部分唯一索引） | 200 |
| `/model-configs/{id}/test` | POST | **真实调用上游**：聊天校验 `response_format=json` 契约；Embedding 校验**实际维度与声明维度一致**（不符报 `embedding_dim_mismatch`） | 200，`ok/latencyMs/errorCode/detail` |

稳定错误码：`model_auth_failed`（401/403，不可重试）、`model_unavailable`（超时/连接失败/限流 429/5xx，
最多重试 3 次指数退避）、`model_request_rejected`（其余 4xx，以及 **429 + 额度耗尽**——
同一状态码承载两种语义，按上游 `code`/`type`/文案区分，后者不可重试）、`model_config_invalid`（503，
真实模式缺配置时**绝不降级为 Mock**）。

## 2. 操作申请与审批 `/api/v1/action-requests`（仅坐席与管理员）

关闭与转派是 HIGH_RISK 动作：模型**只能提议**，人必须审批，动作执行与执行账本同事务。

| 接口 | 方法 | 说明 | 成功结果 |
| --- | --- | --- | --- |
| `/action-requests?status=PENDING` | GET | 按状态列出（默认待审批） | 200 |
| `/action-requests/{id}` | GET | 详情（含不可变参数中的理由、发起时的工单版本） | 200 |
| `/action-requests/{id}/ledger` | GET | 执行记录（只追加，无删除接口） | 200 |
| `/action-requests/{id}/decide` | POST | 批准/拒绝；需 `Idempotency-Key` | 200，`executed/blockedReason/ledger/request` |

状态机：`PENDING → APPROVED / REJECTED / EXPIRED`（终态），由条件更新（`WHERE status='PENDING'`）
保证并发双审只成功一次。

幂等语义（AGENTS.md §6）：**决策是状态迁移而非创建**——重复决策返回
`409 action_request_not_pending`，不重放首次结果；动作至多执行一次由账本的
`action_request_id` 与 `idempotency_key` 两个唯一约束兜底。

不执行的条件与稳定错误码：`action_request_expired`（过期，由 Worker 轮询前的清扫独占写入 EXPIRED）、
`ticket_version_changed`（申请后工单版本变化，授权前提不成立）、`ticket_already_closed`（终态重复关闭）。

运行联动（对运行记录的可见效果）：批准并执行 → 运行 `COMPLETED`；拒绝 / 过期 → 运行 `NEEDS_HUMAN`。
运行停在等待审批时状态为 `WAITING_APPROVAL`（非终态，释放租约，不写 `finished_at`）。

## 3. 评测 `/api/v1/evaluations`（仅管理员）

| 接口 | 方法 | 说明 | 成功结果 |
| --- | --- | --- | --- |
| `/evaluations/import` | POST | 导入冻结评测集（50 条）与冻结语料（12 篇）；按 `caseKey` 幂等 | 200，`created/reused/corpusDocs` |
| `/evaluations/runs` | POST | 执行评测；`mode` 为 `mock` / `real`（Mock 与真实结果分别落库），`limit` 可选 | 201，运行记录含 `metrics` |
| `/evaluations/runs/{id}` | GET | 运行详情 | 200 |
| `/evaluations/runs/{id}/report` | GET | **JSON 报告导出**：聚合指标 + 逐用例结果 | 200 |

指标口径：分母只计**适用**用例（不适用记 `null`，缺测不等于失败）。当前已实现
`category`（准确率，目标 ≥0.9）与 `recall_at_5`（目标 ≥0.8），指标对象内嵌目标与达标布尔。
安全场景的「转人工」考核需要完整运行，当前记 `null`（待安全闸实现后补齐）。
`indexVersion` 记录评测时的索引版本：换索引或换 Embedding 模型后必须重新评测。

## 4. 运行与事件（沿用两段式 SSE 协议）

`POST /tickets/{id}/runs`（坐席/管理员，可按次指定 `model_mode`）返回 `202 + run_id`，
事件从**持久化记录**读取（`GET /runs/{id}/events`，支持 `Last-Event-ID` 续读），
断线重连不触发重新运行或重复持久化。新增事件类型：`approval.required`。

## 5. 变更流程

新增或变更上述任何契约时：先更新本文件与 OpenAPI（FastAPI 自动生成，前端类型从 OpenAPI 生成），
再实现；破坏性变更必须在响应中体现版本或提供兼容期。
