> ⚠️ **已退役 · 旧 Java 架构证据**：本文描述的架构已被 Python 全栈重构替代（ADR-0008，`codex/supportflow-agent-python`）。
> 内容仅作历史证据保留，不代表当前系统；现行基线以仓库根目录的 `PLAN.md` 与 `AGENTS.md` 为准。

# ADR 0003：租户隔离

## 决策

业务表均含 `tenant_id`；MyBatis-Plus 租户拦截器追加过滤，身份基础表显式豁免。

## 替代方案

每租户独立库、仅靠调用方手写 where 条件。

## 后果与回滚

缺失认证上下文的租户 SQL 会失败；离线任务需显式设置上下文。
