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
PLAYWRIGHT_BASE_URL=http://localhost:5173 \
npm --prefix frontend run test:e2e
```

该用例覆盖消费者注册、创建会话、人工转接 SSE，以及坐席登录、认领工单、记录内部备注、解决并关闭工单；GitHub Actions 会自动执行它。

## Docker 基础设施

复制环境变量模板后启动依赖服务：

```bash
cp .env.example .env
docker compose up -d
```

Docker Compose 当前提供依赖服务和后端镜像构建入口。账号与密码仅适用于本地开发，禁止把真实密钥写入 `.env.example` 或提交到仓库。启动 backend profile 前需要设置 `SUPPORTFLOW_JWT_SECRET_BASE64`。

## 验证

```bash
mvn -B -f backend/pom.xml test
cd frontend && npm run build
docker compose config --quiet
```

架构与接口说明见 [docs/architecture.md](docs/architecture.md)、[ER 图](docs/er-diagram.md)、[身份契约](docs/contracts/authentication.md)、[幂等契约](docs/contracts/idempotency.md) 和 [docs/adr](docs/adr)。
