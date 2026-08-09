# 身份接口契约（v1）

成功响应直接返回业务 JSON；失败响应使用 RFC 9457 `ProblemDetail` 并包含 `code`、`requestId`。

| 接口 | 认证 | 请求关键字段 | 成功结果 |
| --- | --- | --- | --- |
| `POST /api/v1/tenants/register` | 否 | tenantCode、tenantName、email、displayName、password | 201，tenantId/userId/membershipId |
| `POST /api/v1/customers/register` | 否 | tenantCode、email、displayName、password | 201，创建 CUSTOMER 成员 |
| `POST /api/v1/auth/login` | 否 | tenantCode、email、password | 200，accessToken、refreshToken |
| `POST /api/v1/auth/refresh` | 否 | refreshToken | 200，新 token 对；旧 refresh token 失效 |
| `POST /api/v1/auth/logout` | 否 | refreshToken | 204，撤销令牌 |
| `POST /api/v1/auth/change-password` | Bearer | currentPassword、newPassword | 204，撤销本租户 refresh token |
| `POST /api/v1/admin/members` | TENANT_ADMIN | email、displayName、password、role | 201，创建 AGENT 或 SUPERVISOR |
| `PATCH /api/v1/admin/members/{id}/status` | TENANT_ADMIN | status | 204，禁用时撤销该成员令牌 |

Access token 的角色、租户和成员信息只能由服务端签发。`INVALID_CREDENTIALS` 始终使用 401，避免泄露账号是否存在。
