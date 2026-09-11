# ADR 0008：Python 全栈重构（Java 版封存）

## 状态

已接受，2026-09-11。本决策取代 ADR 0001–0007 所描述的运行时技术栈；被取代的 ADR 保留为历史记录，在阶段 5 统一标注为旧版证据。

## 决策

SupportFlow AI 以**整仓重写**方式迁移为 Python 全栈，产品形态从「企业级多租户售后平台」收敛为「单工作区智能客服工单助手」，核心闭环固定为：

**提交工单 → 内容清洗与分类 → 检索知识库与历史工单 → 按需调用查询工具 → 生成带引用草稿 → 人工审核回复及操作 → 保存处理结果与运行记录。**

技术栈替换如下：

| 能力 | 旧版（Java） | 新版（Python） |
| --- | --- | --- |
| 运行时 | Java 21、Spring Boot 3.5、虚拟线程 | Python 3.13、uv、FastAPI、SQLAlchemy 2 |
| Agent 编排 | 自研工具调用链 | LangGraph + PostgreSQL 持久化检查点 |
| 事务数据库 | MySQL 8.4 + Flyway | PostgreSQL 17 + Alembic |
| 检索 | Elasticsearch 8（BM25 + kNN + RRF） | PostgreSQL 全文检索 + pgvector（RRF 融合） |
| 事件缓存 / SSE | Redis Stream | PostgreSQL 分区事件表 |
| 可靠消息 | RocketMQ + Outbox + 消费幂等 | 同库事务 + 租约领取 + 执行账本幂等 |
| 对象存储 | MinIO | 持久化卷 + `object_key` 引用 |
| 前端 | React 19 + Tauri 桌面壳 | React + TypeScript + Vite（仅 Web） |
| 测试 | JUnit 5 + Testcontainers + WireMock | pytest + Testcontainers + respx + Playwright |

同步确立三项范围收缩：

- **单工作区**：删除多租户、`tenant_id` 与全部租户隔离机制，角色收敛为 `USER` / `AGENT` / `ADMIN`。
- **工单状态简化**：`OPEN → CLOSED`，`CLOSED` 为终态；转派只修改负责人；不含 SLA 策略、优先级与延时消息提醒。
- **取消桌面分发**：不承接 Tauri 打包、jpackage sidecar、DMG 签名与公证链路。

旧版基线 `f4f02d6` 与一个额外 worktree 封存到仓库外目录，包含 Git bundle（全 refs 与 stash）、未跟踪文件快照与哈希清单；旧数据保留但**不迁移**，新版使用独立数据库与独立数据卷。

新架构细节以 [PLAN.md](../../PLAN.md) 为准，开发行为约束以 [AGENTS.md](../../AGENTS.md) 为准。

## 替代方案

- **保留 Java 后端，仅用 LangGraph 重写 Agent 层**：可保留已验收的 115 项测试与 93.65% 行覆盖率，但会形成「Java + Python 双运行时」的跨语言边界，Agent 与业务服务之间需要额外的 RPC、契约与部署单元；净收益低于整仓重写。
- **保留 Java，用 Spring AI / LangChain4j 自研编排**：技术栈单一，但 LangGraph 的持久化检查点、显式状态图与中断恢复语义需要自行实现，等于重做本次重构中最需要外部成熟度的部分。
- **增量演进旧版（继续补齐 evaluation / analytics 模块）**：改动最小，但产品叙事仍是多租户企业平台，与「personal-use 单工作区工单助手」的目标一致，「单数据库、可一键起停」的交付叙事无法成立。
- **维持 Java 主链路 + 独立 Python Agent 服务**：可渐进迁移且风险可控，但引入分布式一致性、跨服务鉴权与两套测试体系，与本次「压缩部署与验收成本」的动机直接冲突。

## 后果与回滚

**收益**

- 中间件从 5 类（MySQL / Redis / Elasticsearch / MinIO / RocketMQ）压缩为 1 类（PostgreSQL 17 + pgvector），容器编排、故障演练与验收成本显著下降。
- Agent 编排交由 LangGraph，直接获得显式状态图、持久化检查点与中断恢复语义，无需自研。
- 产品叙事收敛为单工作区工单助手，演示动线缩短，验收标准可量化（50 条冻结评测集、分类准确率 ≥90%、Recall@5 ≥80%）。
- 开发环境与 CI 共用 `uv.lock`，依赖可复现性优于旧版 Maven + npm 双锁。

**代价与已知风险**

- 21 个未跟踪的 Java `evaluation` / `analytics` 收尾文件在新版中作废，必须在阶段 1 封存后方可继续，否则构成不可恢复的工作丢失。
- 旧版已验收证据（115 项测试、93.65% 行覆盖率、k6 压测结果、DMG 构建链路）不再适用于新架构，简历与演示材料需重写；新的覆盖率门槛分阶段生效，阶段 3 前不构成门禁。
- 去掉租户隔离后，「跨租户访问被拒绝」这一原有回归场景失效，须替换为角色越权场景覆盖，否则会出现覆盖真空。
- 检索质量基线整体重置：旧版 Elasticsearch 的 BM25 调参与阈值不可迁移，需在 100 条 dev set 上重新校准门槛。
- 取消桌面分发后，本机自用形态退化为需要自行启动 Compose；ADR 0007 所解决的「双击即用」体验不再提供。

**回滚**

- 回滚点位于提交 `f4f02d6`：`git show f4f02d6:PLAN.md` 与 `git show f4f02d6:AGENTS.md` 可取回旧架构基线与规范。
- 旧版代码在封存 bundle 与保留的 Git 历史中完整可达，可在任何时间 checkout 并重建；旧数据库卷未删除，可与旧代码配对恢复。
- 新版与旧版使用**独立数据库、独立数据卷与独立 Compose 项目名**，互不阻塞，可并行存在。
- 阶段 1 完成封存验证后本决策不可逆点即已消除；在此之前不得删除旧版分支、stash 或未跟踪文件。
