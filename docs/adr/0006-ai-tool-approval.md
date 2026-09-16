> ⚠️ **已退役 · 旧 Java 架构证据**：本文描述的架构已被 Python 全栈重构替代（ADR-0008，`codex/supportflow-agent-python`）。
> 内容仅作历史证据保留，不代表当前系统；现行基线以仓库根目录的 `PLAN.md` 与 `AGENTS.md` 为准。

# ADR 0006：AI 工具审批

## 决策

工具按 READ_ONLY、LOW_RISK、HIGH_RISK 分级；退款与补偿只创建审批，禁止模型直接执行。

## 替代方案

模型直接调用退款接口。

## 后果与回滚

多一步人工流程但可审计；审批策略可配置，不改变高风险默认值。
