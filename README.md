# SupportFlow Agent 智能客服工单助手

面向**精简电商售后场景**的智能客服工单助手，覆盖配送咨询、退换货政策、商品使用和投诉处理，形成一条完整的人工在环闭环：

**提交工单 → 内容清洗与分类 → 检索知识库与历史工单 → 按需调用查询工具 → 生成带引用的草稿 → 人工审核回复及操作 → 保存处理结果与运行记录。**

完整架构、模块设计、数据模型、接口契约、实施阶段与验收标准见 [PLAN.md](PLAN.md)；开发行为约束见 [AGENTS.md](AGENTS.md)。

## 仓库当前状态

| 项 | 状态 |
|---|---|
| 文档基线 | 已切换为 Python 版（`PLAN.md`、`AGENTS.md`、[ADR 0008](docs/adr/0008-python-fullstack-rewrite.md)） |
| Python 工程 | **阶段 2 已交付**：可运行的工单提交 → 持久化 → Agent 分类闭环（Mock 模型） |
| 旧版归档 | 阶段 1 已封存（Git bundle + 快照 + 恢复验证 20/20 通过） |
| `backend/` 目录 | 仍是已封存的旧 Java 代码，**不再演进**，阶段 5 删除 |
| `frontend/` 目录 | 仍是旧 Java 版的 React + Tauri 前端，将在阶段 4 替换；当前用 `/docs`（OpenAPI）代替页面 |
| 测试 | 148 个用例（73 单测 + 75 集成，集成基于 Testcontainers 真实 PostgreSQL），行覆盖率 92% |
| 容器环境 | `docker compose up` 一键启动：postgres → migrate → seed → api + worker |

阶段 2 已验收：提交工单 → 202 + 持久化 → 刷新后仍可查询 → Worker 自动分类 → SSE 事件流回放 → **容器重启后数据保留**。

## 产品闭环

```mermaid
flowchart LR
    Submit["提交工单"] --> Clean["内容清洗"]
    Clean --> Classify["标准化分类"]
    Classify --> Retrieve["混合检索<br/>FAQ / 文档 / 历史工单"]
    Retrieve --> Tools{"按需调用查询工具"}
    Tools --> Draft["生成带引用草稿"]
    Draft --> Verify{"引用归属校验"}
    Verify -->|通过| Review["坐席审核 / 编辑"]
    Verify -->|检索为空或证据不足| Human["转人工"]
    Review --> Publish["发布正式回复"]
    Review --> Propose["申请关闭 / 转派"]
    Propose --> Approve{"人工审批"}
    Approve -->|批准| Execute["执行并写入执行账本"]
    Approve -->|拒绝 / 过期 / 版本变化| Review
    Publish --> Trace["保存处理结果与运行记录"]
    Execute --> Trace
    Human --> Review
```

## 技术栈

| 部分 | 选型 |
|---|---|
| Python 工程 | Python 3.13、uv（依赖与虚拟环境）、Pydantic v2 |
| 后端 | FastAPI、SQLAlchemy 2、Alembic、psycopg 3 |
| Agent | LangGraph、PostgreSQL 持久化检查点 |
| 数据与检索 | PostgreSQL 17、pgvector、中文分词后的全文检索 |
| 前端 | React、TypeScript、Vite |
| 验证 | pytest、pytest-cov、HTTPX / respx、Testcontainers、Playwright |
| 部署 | Docker Compose：网页、API、Worker、数据库 |

运行时**只依赖 PostgreSQL 一类中间件**——检索（全文 + 向量）、事件缓存（分区事件表）、可靠执行（同库事务 + 执行账本）全部落在同一数据库内，不再引入 Redis、Elasticsearch、MinIO 或 RocketMQ。

## 目标目录结构

```text
src/supportflow/
├── identity/       用户、会话、角色与访问控制
├── ticket/         工单、内容清洗、分类、状态机
├── knowledge/      文档与历史导入、切片、索引、检索、引用
├── model/          聊天与 Embedding 网关、密钥加密、连接测试
├── agent/          LangGraph 状态图、工具注册表、运行记录
├── approval/       操作申请、审批与执行账本
├── evaluation/     评测集、评测运行与报告导出
├── shared/         配置、日志、错误协议、幂等、数据库、SSE
└── bootstrap/      FastAPI 装配、依赖注入、Worker 入口
```

每个模块内部按 `api -> application -> domain <- infrastructure` 分层，边界由自动化契约测试固化。

## 快速开始

### 一键启动（推荐）

```bash
cp .env.example .env
docker compose up --build
```

服务就绪后访问 <http://localhost:8000/docs> 查看接口文档。演示账号（本地 only）：

| 邮箱 | 角色 | 口令 |
|---|---|---|
| `customer@example.com` | USER | `demo1234` |
| `agent@example.com` | AGENT | `demo1234` |
| `admin@example.com` | ADMIN | `demo1234` |

最小闭环（登录 → 提交工单 → Worker 自动分类 → 查询结果）：

```bash
BASE=http://localhost:${API_PORT:-8000}
curl -c /tmp/sf.jar -X POST $BASE/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"customer@example.com","password":"demo1234"}'
CSRF=$(grep sf_csrf /tmp/sf.jar | awk '{print $7}')
curl -b /tmp/sf.jar -X POST $BASE/api/v1/tickets \
  -H 'Content-Type: application/json' \
  -H "X-CSRF-Token: $CSRF" -H 'Idempotency-Key: my-first-ticket-01' \
  -d '{"subject":"快递没到","body":"订单 A-2026-0901 的快递一直没到"}'
# 数秒后用返回的 run_id / ticket_id 查询：
# GET /api/v1/runs/{run_id}        → status=COMPLETED, step_count=3
# GET /api/v1/tickets/{ticket_id}  → category=DELIVERY（分类已写回）
```

> 写请求必须携带 ≥8 字符的 `Idempotency-Key` 与 `X-CSRF-Token`（取自登录后可读的 `sf_csrf` Cookie）。

### 本地开发

```bash
uv sync                                              # 按 uv.lock 安装依赖
docker compose up -d postgres                        # 只起数据库
uv run alembic upgrade head                          # 应用数据库迁移
uv run python -m supportflow.bootstrap.seed          # 预置演示账号
uv run uvicorn supportflow.bootstrap.api:app --reload
uv run python -m supportflow.bootstrap.worker        # 另开终端：Agent Worker
```

> 若宿主机 8000 端口被占用，在 `.env` 里改 `API_PORT` 后重新 `docker compose up -d api`。

### 环境变量

| 变量 | 说明 |
|---|---|
| `DATABASE_URL` | PostgreSQL 连接串，格式 `postgresql+psycopg://...` |
| `MODEL_MODE` | `mock`（默认）或 `real`；Compose 默认 `mock` 以支持无外部依赖演示 |
| `MODEL_SECRET_MASTER_KEY` | 模型 API Key 的 AES-GCM 主密钥，可用 `openssl rand -base64 32` 生成 |
| `UPLOAD_DIR` | 导入原文件的持久化卷挂载路径 |

`MODEL_SECRET_MASTER_KEY` 只允许通过环境变量提供，**不得写入源码、`.env.example`、测试快照或提交历史**。模型的 API Key 由管理员在网页端配置，仅以 AES-GCM 密文保存，查询接口只返回是否已配置。

## 验证

```bash
uv run ruff check .
uv run mypy src
TEST_DATABASE_URL=postgresql+psycopg://supportflow:supportflow@localhost:5432/supportflow_test \
  uv run pytest --cov=supportflow
```

集成测试默认用 Testcontainers 自起 `pgvector/pgvector:pg17` 容器；设置
`TEST_DATABASE_URL` 可复用已运行的 PostgreSQL（推荐，速度更快）。覆盖率门槛**分阶段
生效**：阶段 3 结束时起强制执行行覆盖率 ≥85%、分支覆盖率 ≥75%（阶段 2 当前为 92%）。
Mock 验证结果与真实模型评测结果必须分别报告。

## 文档

| 文档 | 内容 |
|---|---|
| [PLAN.md](PLAN.md) | 架构基线、模块设计、数据模型、接口契约、实施阶段、验收标准 |
| [AGENTS.md](AGENTS.md) | 开发行为规范、模块边界、安全与一致性约束 |
| [ADR 0008](docs/adr/0008-python-fullstack-rewrite.md) | Java → Python 全栈重构的决策、替代方案与回滚点 |

### 旧版归档与待退役文档

新架构取代了 [ADR 0001–0007](docs/adr) 所描述的 Java 运行时。旧版基线为提交 `f4f02d6`，封存于仓库外的归档目录（含 Git bundle、未跟踪文件快照与哈希清单）；旧架构基线可用 `git show f4f02d6:PLAN.md` 取回。

以下文档描述的是**已退役的 Java 架构**，将于阶段 5 统一退役并标注为旧版证据。在退役完成前，任何与其冲突的实现一律以 `PLAN.md` 与 `AGENTS.md` 为准：

- `docs/adr/0001-0007`、`docs/architecture.md`、`docs/er-diagram.md`
- `docs/openapi.yaml`、`docs/contracts/`
- `docs/reports/`（含旧版测试、性能与 RAG 评测证据，**不可与新评测集混用**）
- `docs/demo-runbook.md`、`docs/resume-project-description.md`

以下配置与脚本仍是旧版产物、将于阶段 5 统一退役（`docker-compose.yml` 与
`.env.example` 已在阶段 2 替换为 Python 版）：

- `script/`、`scripts/`、`perf/`、`infra/`（构建、验收与压测脚本均针对旧 Java 栈）

旧 Java 版的启动方式（Maven、Tauri 桌面壳、Elasticsearch / Redis / MinIO / RocketMQ Compose 配置）随旧版一并失效。
