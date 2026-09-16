> ⚠️ **已退役 · 旧 Java 架构证据**：本文描述的架构已被 Python 全栈重构替代（ADR-0008，`codex/supportflow-agent-python`）。
> 内容仅作历史证据保留，不代表当前系统；现行基线以仓库根目录的 `PLAN.md` 与 `AGENTS.md` 为准。

# ADR 0002：认证上下文传播

## 决策

JWT access token 解析为 `AuthenticatedPrincipal`，请求期间写入 `TenantContext`，请求完成必清理。

## 替代方案

客户端传 tenantId、每个接口重复解析 JWT。

## 后果与回滚

业务接口不能接受 tenantId；异步任务必须显式建立上下文，未来可替换为 Reactor Context。
