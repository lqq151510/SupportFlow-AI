# SupportFlow AI

企业级电商售后客服与工单协同平台。项目以模块化单体实现多租户隔离、RAG、可靠流式会话、工单 SLA 及人工审批的高风险动作闭环。

完整架构与阶段目标见 [PLAN.md](PLAN.md)，开发行为见 [AGENTS.md](AGENTS.md)。

## 当前基线

- 后端：Java 21、Spring Boot、Spring Security、Spring Modulith、Actuator。
- 前端：React、TypeScript、Vite。
- 本地基础设施：MySQL、Redis、Elasticsearch、MinIO、RocketMQ。
- 当前提交只提供工程骨架；身份、数据库业务迁移及 Docker 环境下的完整业务联调将在后续功能提交中实现。

## 本地启动

```bash
cd backend
mvn spring-boot:run
```

启动后访问 `GET http://localhost:8080/actuator/health`。每个响应都会带上 `X-Request-Id`，调用方也可以自行传入该请求头。

前端开发：

```bash
cd frontend
npm install
npm run dev
```

## Docker 基础设施

复制环境变量模板后启动依赖服务：

```bash
cp .env.example .env
docker compose up -d
```

Docker Compose 当前提供依赖服务和后端镜像构建入口。账号与密码仅适用于本地开发，禁止把真实密钥写入 `.env.example` 或提交到仓库。
