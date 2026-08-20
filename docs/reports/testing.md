# 第 8 周测试验收报告

- 执行时间：2026-08-12
- 环境：macOS arm64、Java 21.0.10、Spring Boot 3.5.14、Node.js 22
- 范围：后端单元/架构/真实容器测试、覆盖率、前端组件测试与构建、浏览器主流程、完整 Compose、故障恢复、安全与交付材料

## 后端质量门禁

执行：

```zsh
mvn -B -f backend/pom.xml clean verify
```

- 测试：115
- 失败：0
- 错误：0
- 跳过：0
- Flyway：H2 与真实 MySQL 的 V1～V23 全部迁移成功
- 架构：Spring Modulith 边界与 ArchUnit 规则通过
- JaCoCo 行覆盖率：93.65%（1268/1354），`verify` 门禁要求至少 85%
- JaCoCo 分支覆盖率：75.38%（499/662），`verify` 门禁要求至少 75%
- 模型 HTTP/SSE：OpenAI-compatible、Anthropic、503 与流超时测试通过；WebClient 使用 Reactor Netty，超时取消不再产生 `onErrorDropped` 伪错误
- Java 21+ 测试运行时：Surefire 通过 Maven 依赖属性显式加载 Mockito Agent，与 JaCoCo Agent 同时启用；另以 `-Djacoco.skip=true` 验证单独运行 Mockito Agent，均无动态自挂载警告
- 结果：通过

复验（2026-08-20，macOS arm64、Java 21.0.10、Docker Desktop 29.7.2）：`mvn -B -f backend/pom.xml verify` 通过，120 项测试无失败、错误或跳过；JaCoCo 行覆盖率为 93.56%（1526/1631），分支覆盖率为 75.90%（551/726），继续满足 85%/75% 门禁。Elasticsearch 容器在 8.31 秒内启动，RocketMQ 容器场景在 19.88 秒内通过。

全量交付复验（2026-08-20）：`./scripts/verify-delivery.sh` 与 CI 地址组合下的 Playwright 主流程均通过；前端 Vitest 4/4、TypeScript/Vite 生产构建、Compose 配置解析、两条 k6 脚本解析均通过，Playwright 的管理端与消费者到坐席闭环为 2/2。浏览器验收必须使用 `http://localhost:5173`，与后端 CORS 默认允许源保持一致。

完整 Compose 复验（2026-08-20）：以临时 JWT/模型主密钥启动 `app` profile，并因宿主机 9000/9001 已被其他服务占用而仅对本次运行使用 MinIO `19000/19001` 映射；MySQL、Redis、MinIO、RocketMQ NameServer/Broker、后端与前端均启动，后端 `/actuator/health` 返回 `UP`，前端返回 HTTP 200，Redis `PONG`，RocketMQ `support-domain-events` 路由可见。单节点 Elasticsearch 的 `supportflow-knowledge` 默认副本无法分配时，首次验收将该索引副本数临时调为 0 后集群为 `green`（100% active shards）；随后在 Compose 中加入 Elasticsearch 初始化服务，安装 `supportflow-*` 副本数为 0 的索引模板。真实模板读取与 simulate-index 验证均确认未来索引会继承该设置。验收后执行 `docker compose --profile app down`，未删除任何命名卷。

默认 profile 不启用 Redis Stream，因此关闭 Redis 健康指示器；Docker profile 显式重新启用。无 Redis 的默认启动下 `/actuator/health` 返回 `UP`，避免测试和 E2E 把未启用的外部依赖误判为应用故障。

## 前端质量门禁

```zsh
npm --prefix frontend run test:unit
npm --prefix frontend run build
```

- Vitest：1 个测试文件、4 个测试，全部通过
- TypeScript：通过
- Vite：1795 个模块构建成功
- 主 JavaScript 产物：242.14 kB，gzip 74.99 kB
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
- Playwright：管理端知识库/模型配置与消费者到坐席闭环 2/2 通过；录屏场景独立通过
- 演示录像：[supportflow-demo.webm](../demo/supportflow-demo.webm)
- 录像时长：180.08 秒（约 3 分钟）
- 录像大小：9,887,967 字节
- 结果：通过

## 安全与供应链

- Gitleaks 8.30.1：扫描完整 Git 历史，0 泄漏
- Gitleaks Action v3：CI 运行时升级至 Node.js 24，并固定使用 Gitleaks 8.30.1；扫描配置与行为保持不变
- `npm audit --omit=dev --audit-level=high`：生产依赖 0 漏洞
- GitHub Actions：后端、前端、Dependency Review、Gitleaks、CodeQL 门禁已配置
- CI YAML：通过 `Psych.parse_file` 纯语法解析
- 结果：通过

## 性能

普通 API 100 RPS 与 100 并发 SSE 均已达到门槛，详见[性能报告](performance.md)。

## Docker 与真实中间件

- Testcontainers：MySQL + Redis、Elasticsearch 8.17.3、RocketMQ 5.3.2 共 3/3 通过；RocketMQ 场景同时验证普通事件即时消费与 SLA 绝对截止时间延时投递
- 复验（2026-08-20，macOS arm64、Docker Desktop 29.7.2、Java 21.0.10）：`mvn -B test '-Dtest=ElasticsearchContainerIntegrationTest,RocketMqContainerIntegrationTest'` 通过；Elasticsearch 1/1（13.06 秒），RocketMQ 1/1（23.37 秒）。Docker daemon 可访问，两个测试均实际启动对应容器；未发现需要调整 `backend/pom.xml` 或测试实现的问题。
- Compose：MySQL、Redis、Elasticsearch、MinIO、RocketMQ NameServer/Broker、后端与前端完整启动
- 健康证据：后端 `UP`、前端 HTTP 200、Elasticsearch green、Redis PONG、MySQL 23 个迁移成功、RocketMQ `support-domain-events` 路由可见
- 故障恢复：Redis 与 RocketMQ Broker 停机路径均确认并自动恢复，恢复后后端健康仍为 `UP`
- 构建性能：后端首次冷构建约 9 分 32 秒；启用 BuildKit Maven 缓存后，无源码变化的二次构建约 1 秒，单次源码增量构建并执行 102 个镜像内测试约 32 秒
- 本机 MinIO 验收因 9000/9001 端口占用，使用 19000/19001 映射和已缓存的 `RELEASE.2023-03-20T20-16-18Z`；Compose 默认仍固定 2025 tag，并允许 `MINIO_IMAGE` 覆盖

Docker 最终阶段已通过，可以创建 `v1.0.0-demo` 标签。
