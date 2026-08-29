# SupportFlow AI

企业级电商售后客服与工单协同平台。项目以模块化单体实现多租户隔离、RAG、可靠流式会话、工单 SLA 及人工审批的高风险动作闭环。

RAG 的 50 条冻结评测集、质量门槛与适用边界见 [RAG 评测基线](docs/reports/rag-evaluation.md)。

完整架构与阶段目标见 [PLAN.md](PLAN.md)，开发行为见 [AGENTS.md](AGENTS.md)。

## 当前基线

- 后端：Java 21、Spring Boot、Spring Security、Spring Modulith、MyBatis-Plus、Flyway、Actuator。
- 前端：React、TypeScript、Vite。
- 本地基础设施：MySQL、Redis、Elasticsearch、MinIO、RocketMQ。
- 已完成租户管理员和消费者注册、JWT 登录/刷新/登出、改密、成员管理与角色访问控制。
- 已完成 refresh token 轮换与撤销、请求 ID、RFC 9457 错误响应、Spring Modulith 与 ArchUnit 架构校验。
- Mock Commerce 已提供消费者演示订单查询；订单租户条件由认证上下文与 MyBatis-Plus 租户拦截器强制派生。

## 本地启动

```bash
cd backend
mvn spring-boot:run
```

启动后访问 `GET http://localhost:8080/actuator/health`。每个响应都会带上 `X-Request-Id`，调用方也可以自行传入该请求头。

前端开发：

```bash
cd frontend
npm ci
npm run dev
```

## macOS 本地客户端

Apple Silicon Mac 可以通过项目级入口同时启动本地持久化 H2 后端和 Tauri 客户端；桌面版默认不启用本地 Mock 模型，而是使用在应用内保存的云端模型 API 配置。后端未运行时，登录页会显示连接状态并提供重新检测：

```bash
./script/build_and_run.sh
```

该入口只会停止当前仓库构建出的 Tauri 进程；若 8080 端口已有健康的 SupportFlow 后端则直接复用，否则以 `desktop` profile 启动后端，并在客户端退出时一并停止。首次启动会在 macOS Keychain 创建一把仅本机可用的模型加密主密钥；后续启动读取同一把密钥，避免已保存的模型配置无法解密。登录租户管理员后，在“模型配置”中添加并测试 `OPENAI_COMPATIBLE` 或 `ANTHROPIC_MESSAGES` 的云端端点、模型名和 API Key，再设为默认模型。API Key 仅在保存/测试时提交并以 AES-GCM 加密保存，不能也不应写入 `.env`、源码或日志。H2 数据位于 `~/Library/Application Support/SupportFlow AI/data/`，后端日志位于 `~/Library/Application Support/SupportFlow AI/logs/backend.log`，均不进入仓库。

若要把数据存放到其他目录（例如隔离测试），可以显式覆盖：

```bash
SUPPORTFLOW_DESKTOP_DATA_DIR="/tmp/supportflow-desktop-test" ./script/build_and_run.sh
```

运行完整 macOS 单测、DMG 构建和磁盘映像校验：

```bash
./script/build_and_run.sh --verify
```

DMG 输出位于 `frontend/src-tauri/target/release/bundle/dmg/`。发行物内嵌本机后端辅助进程：8080 没有健康的 SupportFlow 后端时，应用会启动该进程并使用持久化 H2；关闭客户端时会停止自己启动的进程。模型仍只通过管理员保存的云端 API 配置调用。需要 MySQL、Redis、Elasticsearch、MinIO 与 RocketMQ 的完整功能时，仍使用下方 Docker Compose 环境。

## 浏览器验收

先启动后端与前端开发服务，再运行消费者到坐席的真实主流程：

```bash
SUPPORTFLOW_API_BASE_URL=http://localhost:8080 \
VITE_API_BASE_URL=http://localhost:8080 \
PLAYWRIGHT_BASE_URL=http://localhost:5173 \
npm --prefix frontend run test:e2e
```

若 Playwright 专用 Chromium 尚未下载，macOS 可直接复用系统 Google Chrome：

```bash
SUPPORTFLOW_API_BASE_URL=http://localhost:8080 \
VITE_API_BASE_URL=http://localhost:8080 \
PLAYWRIGHT_BASE_URL=http://localhost:5173 \
npm --prefix frontend run test:e2e:macos
```

快速 E2E 覆盖管理端知识库与模型配置，以及消费者注册、创建会话、人工转接 SSE、坐席认领、备注、解决和关闭工单；GitHub Actions 会自动执行它。需要重新生成约 3 分钟的演示录像时，单独运行 `npm --prefix frontend run test:demo`，避免录屏等待拖慢日常反馈。

## Docker 基础设施

复制环境变量模板后，可以一键构建并启动完整本地环境：

```bash
cp .env.example .env
docker compose --profile app up --build
```

启动后，前端为 http://localhost:5173，后端健康检查为 http://localhost:8080/actuator/health。容器前端会通过同源 `/api` 转发请求给后端，不依赖浏览器直连后端端口。若只需启动中间件，使用 `docker compose up -d`。

若本机已有服务占用 MinIO 默认端口，可在 `.env` 中设置 `MINIO_API_PORT` 和 `MINIO_CONSOLE_PORT`；该设置只改变宿主机映射，容器内应用仍通过 `minio:9000` 访问。`MINIO_IMAGE` 可在镜像下载受限时临时覆盖固定的 2025 tag；本机 Docker 验收使用了已缓存的 `RELEASE.2023-03-20T20-16-18Z`。Compose 会在 Broker 健康后显式创建 `support-domain-events`，并在 Elasticsearch 健康后安装 `supportflow-*` 单节点索引模板（副本数为 0）；后端仅在这两个初始化步骤成功后启动。

账号、密码和 JWT 密钥仅适用于本地开发，禁止把真实生产密钥写入 `.env.example` 或提交到仓库；完整应用启动前需在 `.env` 中设置 `SUPPORTFLOW_JWT_SECRET_BASE64` 和 `MODEL_SECRET_MASTER_KEY`，后者可用 `openssl rand -base64 32` 生成。Compose 默认以 `SUPPORTFLOW_MODEL_MOCK_ENABLED=true` 提供无需外部 API Key 的确定性聊天与向量化演示；完成真实模型配置后可改为 `false`，启用 OpenAI-compatible/Anthropic 网关。

## 验证

完整交付校验要求 Docker daemon 已启动；脚本会在 Maven 前显式检查它，以避免 `disabledWithoutDocker` 让真实容器测试被跳过后仍误报成功：

```bash
./scripts/verify-delivery.sh
```

仅复验 Elasticsearch 与 RocketMQ 的真实容器链路时，使用：

```bash
docker info
mvn -B -f backend/pom.xml test \
  '-Dtest=ElasticsearchContainerIntegrationTest,RocketMqContainerIntegrationTest'
```

这会拉起隔离的 Elasticsearch 8.17.3、RocketMQ NameServer/Broker；不依赖 Compose 已启动的服务。完整 Compose 配置可先用 `docker compose config --quiet` 进行无副作用校验。

完整 Compose 启动完成后，使用以下命令验证应用层与关键中间件的运行态；该脚本不启动、停止或修改服务：

```bash
./scripts/verify-compose-runtime.sh
```

故障演练、压测和演示步骤见 [演示与故障验证手册](docs/demo-runbook.md)，验收证据见[测试报告](docs/reports/testing.md)与[性能报告](docs/reports/performance.md)，最终简历表述见 [简历项目描述](docs/resume-project-description.md)。

架构与接口说明见 [docs/architecture.md](docs/architecture.md)、[ER 图](docs/er-diagram.md)、[OpenAPI 3.1](docs/openapi.yaml)、[身份契约](docs/contracts/authentication.md)、[幂等契约](docs/contracts/idempotency.md) 和 [docs/adr](docs/adr)。
