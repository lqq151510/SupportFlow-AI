# 第 8 周测试验收报告

- 执行时间：2026-08-12
- 环境：macOS arm64、Java 21.0.10、Spring Boot 3.5.14、Node.js 22
- 范围：后端非容器测试、覆盖率、前端组件测试与构建、浏览器主流程、安全与交付材料

## 后端质量门禁

执行：

```zsh
mvn -B -f backend/pom.xml clean test \
  -Dtest='*Test,!InfrastructureContainerIntegrationTest,!ElasticsearchContainerIntegrationTest,!RocketMqContainerIntegrationTest'
```

- 测试：81
- 失败：0
- 错误：0
- 跳过：0
- Flyway：V1～V19 全部迁移成功
- 架构：Spring Modulith 边界与 ArchUnit 规则通过
- JaCoCo 行覆盖率：87.29%（728/834）
- JaCoCo 分支覆盖率：73.71%（370/502）
- 结果：通过

默认 profile 不启用 Redis Stream，因此关闭 Redis 健康指示器；Docker profile 显式重新启用。无 Redis 的默认启动下 `/actuator/health` 返回 `UP`，避免测试和 E2E 把未启用的外部依赖误判为应用故障。

## 前端质量门禁

```zsh
npm --prefix frontend run test:unit
npm --prefix frontend run build
```

- Vitest：1 个测试文件、2 个测试，全部通过
- TypeScript：通过
- Vite：1792 个模块构建成功
- 主 JavaScript 产物：236.20 kB，gzip 73.58 kB
- 结果：通过

## 浏览器端到端

核心主流程使用独立的本地后端 `http://127.0.0.1:18080`，并同时向 Playwright helper 和 Vite 注入该地址：

```zsh
CI=1 \
SUPPORTFLOW_API_BASE_URL=http://127.0.0.1:18080 \
VITE_API_BASE_URL=http://127.0.0.1:18080 \
npm --prefix frontend run test:e2e -- customer-agent-handoff.spec.ts
```

- 场景：消费者注册与登录 -> 提交人工请求 -> 自动转人工 -> 坐席登录 -> 领取 -> 内部备注 -> 解决 -> 关闭
- Playwright：1/1 通过，测试执行约 9.1 秒
- 演示录像：[supportflow-demo.webm](../demo/supportflow-demo.webm)
- 录像时长：185.12 秒（约 3 分 05 秒）
- 录像大小：9,541,272 字节
- 结果：通过

## 安全与供应链

- Gitleaks 8.30.1：扫描 124 个 Git 提交，0 泄漏
- `npm audit --omit=dev --audit-level=high`：生产依赖 0 漏洞
- GitHub Actions：后端、前端、Dependency Review、Gitleaks、CodeQL 门禁已配置
- CI YAML：通过 `Psych.parse_file` 纯语法解析
- 结果：通过

## 性能

普通 API 100 RPS 与 100 并发 SSE 均已达到门槛，详见[性能报告](performance.md)。

## Docker 与真实中间件

- MySQL、Redis Testcontainers：已通过历史验收
- Elasticsearch 8.17.3 Testcontainers：1/1 通过，覆盖写入、关键词检索、向量检索和跨租户过滤
- RocketMQ 5.3.2 Testcontainers：留到 Docker 最终阶段执行
- Docker Compose 整栈、Redis 故障演练：留到 Docker 最终阶段执行

本报告在 Docker 最终验收完成后会补充组合测试、Compose 服务健康状态和故障恢复结果；在此之前不创建 `v1.0.0-demo` 标签。
