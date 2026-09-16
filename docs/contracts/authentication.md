> ⚠️ **已退役 · 旧 Java 架构证据**：本文描述的架构已被 Python 全栈重构替代（ADR-0008，`codex/supportflow-agent-python`）。
> 内容仅作历史证据保留，不代表当前系统；现行基线以仓库根目录的 `PLAN.md` 与 `AGENTS.md` 为准。

# 身份接口契约（v1）

成功响应直接返回业务 JSON；失败响应使用 RFC 9457 `ProblemDetail` 并包含 `code`、`requestId`。

| 接口 | 认证 | 请求关键字段 | 成功结果 |
| --- | --- | --- | --- |
| `POST /api/v1/tenants/register` | 否 | email、displayName、password；tenantCode、tenantName 可选 | 201，tenantId/userId/membershipId/tenantCode；缺省时服务端生成工作区标识 |
| `POST /api/v1/customers/register` | 否 | tenantCode、email、displayName、password | 201，创建 CUSTOMER 成员 |
| `POST /api/v1/auth/login` | 否 | tenantCode、email、password | 200，accessToken、refreshToken |
| `POST /api/v1/auth/refresh` | 否 | refreshToken | 200，新 token 对；旧 refresh token 失效 |
| `POST /api/v1/auth/logout` | 否 | refreshToken | 204，撤销令牌 |
| `GET /api/v1/auth/profile` | Bearer | 无 | 200，当前账户的显示名称、邮箱、角色和所属工作区；不含密码、令牌或模型密钥 |
| `PATCH /api/v1/auth/profile` | Bearer | displayName | 200，更新后的当前账户资料；不能修改邮箱、角色或租户归属 |
| `POST /api/v1/auth/change-password` | Bearer | currentPassword、newPassword | 204，撤销本租户 refresh token |
| `POST /api/v1/admin/members` | TENANT_ADMIN | email、displayName、password、role | 201，创建 AGENT 或 SUPERVISOR |
| `PATCH /api/v1/admin/members/{id}/status` | TENANT_ADMIN | status | 204，禁用时撤销该成员令牌 |

Access token 的角色、租户和成员信息只能由服务端签发。`INVALID_CREDENTIALS` 始终使用 401，避免泄露账号是否存在。

本机桌面端的首次管理员注册不展示 `tenantCode` 或 `tenantName`；服务端生成的 `tenantCode` 仅用于后续认证，并由客户端保存在本机浏览器存储。加入已有工作区的消费者注册仍需由管理员提供租户代码。

个人中心使用 `GET /api/v1/auth/profile` 读取服务端当前身份的真实资料。模型状态仅从管理员的 `GET /api/v1/admin/models` 读取名称、协议、端点和默认标记；API Key 仅在创建、探测时提交，查询接口和个人中心均不会返回或显示明文。
