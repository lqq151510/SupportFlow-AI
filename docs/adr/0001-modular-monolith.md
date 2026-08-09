# ADR 0001：模块化单体

## 决策

以 Spring Modulith 维护 `api -> application -> domain <- infrastructure`，跨模块只用公开契约或领域事件。

## 替代方案

微服务、按技术层分包。

## 后果与回滚

保留单进程事务和低运维成本；若模块独立扩展需求稳定，可按事件契约抽离服务。
