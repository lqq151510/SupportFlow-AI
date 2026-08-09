# ADR 0002：认证上下文传播

## 决策

JWT access token 解析为 `AuthenticatedPrincipal`，请求期间写入 `TenantContext`，请求完成必清理。

## 替代方案

客户端传 tenantId、每个接口重复解析 JWT。

## 后果与回滚

业务接口不能接受 tenantId；异步任务必须显式建立上下文，未来可替换为 Reactor Context。
