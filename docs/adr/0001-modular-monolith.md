> ⚠️ **已退役 · 旧 Java 架构证据**：本文描述的架构已被 Python 全栈重构替代（ADR-0008，`codex/supportflow-agent-python`）。
> 内容仅作历史证据保留，不代表当前系统；现行基线以仓库根目录的 `PLAN.md` 与 `AGENTS.md` 为准。

# ADR 0001：模块化单体

## 决策

以 Spring Modulith 维护 `api -> application -> domain <- infrastructure`，跨模块只用公开契约或领域事件。

## 替代方案

微服务、按技术层分包。

## 后果与回滚

保留单进程事务和低运维成本；若模块独立扩展需求稳定，可按事件契约抽离服务。
