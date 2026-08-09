# SupportFlow AI 架构

项目是 Java 模块化单体。每个业务模块使用 `api -> application -> domain <- infrastructure` 分层，并由 Spring Modulith 与 ArchUnit 测试约束。

当前模块：`identity` 负责租户、成员和令牌；`commerce` 提供演示订单；`shared` 提供认证主体、租户上下文和公共错误协议。

认证成功后，JWT 被解析为 `AuthenticatedPrincipal`。HTTP 过滤器写入 `TenantContext`，并在请求结束时清理。业务 API 不接受客户端提供的 `tenantId`；带 `tenant_id` 的业务 SQL 由 MyBatis-Plus 租户拦截器自动限制。

跨模块依赖只允许公开根包契约或领域事件。例如 `identity.CustomerRegisteredEvent` 被 commerce 消费以初始化演示订单。
