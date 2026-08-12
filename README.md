# SupportFlow AI

企业级电商售后客服与工单协同平台。项目以模块化单体实现多租户隔离、RAG、可靠流式会话、工单 SLA 及人工审批的高风险动作闭环。

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

## 浏览器验收

先启动后端与前端开发服务，再运行消费者到坐席的真实主流程：

```bash
SUPPORTFLOW_API_BASE_URL=http://localhost:8080 \
VITE_API_BASE_URL=http://localhost:8080 \
PLAYWRIGHT_BASE_URL=http://localhost:5173 \
npm --prefix frontend run test:e2e
```

该用例覆盖消费者注册、创建会话、人工转接 SSE，以及坐席登录、认领工单、记录内部备注、解决并关闭工单；GitHub Actions 会自动执行它。

## Docker 基础设施

复制环境变量模板后，可以一键构建并启动完整本地环境：

```bash
cp .env.example .env
docker compose --profile app up --build
```

启动后，前端为 http://localhost:5173，后端健康检查为 http://localhost:8080/actuator/health。容器前端会通过同源 `/api` 转发请求给后端，不依赖浏览器直连后端端口。若只需启动中间件，使用 `docker compose up -d`。

账号、密码和 JWT 密钥仅适用于本地开发，禁止把真实生产密钥写入 `.env.example` 或提交到仓库；完整应用启动前需在 `.env` 中设置 `SUPPORTFLOW_JWT_SECRET_BASE64`。

## 验证

```bash
./scripts/verify-delivery.sh
```

故障演练、压测和演示步骤见 [演示与故障验证手册](docs/demo-runbook.md)，验收证据见[测试报告](docs/reports/testing.md)与[性能报告](docs/reports/performance.md)，最终简历表述见 [简历项目描述](docs/resume-project-description.md)。

架构与接口说明见 [docs/architecture.md](docs/architecture.md)、[ER 图](docs/er-diagram.md)、[OpenAPI 3.1](docs/openapi.yaml)、[身份契约](docs/contracts/authentication.md)、[幂等契约](docs/contracts/idempotency.md) 和 [docs/adr](docs/adr)。
