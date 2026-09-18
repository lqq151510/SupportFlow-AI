# ADR 0007：macOS 桌面单机客户端

## 决策

桌面客户端采用 Tauri 2.0 承载既有 Vue 3 前端，并通过 bundle resources 内嵌一个由 jlink 运行时 + jpackage app-image 组装的 `SupportFlowBackend.app` 辅助进程：客户端启动时检测 8080 健康端点，复用已在运行的后端或拉起内嵌进程，退出时只停止自己启动的进程。数据落在 `~/Library/Application Support/SupportFlow AI/`（持久化 H2，`desktop` profile），模型加密主密钥存 macOS Keychain。

单机形态下中间件按既定端口降级，均不改变业务语义：

| 能力 | 完整栈（Compose） | 桌面单机 |
| --- | --- | --- |
| 数据库 | MySQL | 持久化 H2（MySQL 兼容模式） |
| Outbox 投递 | RocketMQ（重试/DLQ） | `LocalOutboxDeliveryGateway` 进程内投递 |
| SSE 事件缓存 | Redis Stream | `InMemoryGenerationEventStore`（重启后仅靠 MySQL 事实重放） |
| 知识检索 | Elasticsearch 混合检索 | `InMemoryKnowledgeSearchIndex` |
| 对象存储 | MinIO | `InMemoryKnowledgeObjectStorage` |

签名策略定为**个人自用、零成本**：本机构建产物采用 ad-hoc 签名，不购买 Apple Developer ID、不做公证。本机构建的 app 不带 `com.apple.quarantine` 扩展属性，Gatekeeper 不拦截，本机可直接双击运行。该决策的代价是 DMG 不能合规分发给他人；若未来需要分发，再升级为 Developer ID 签名 + 公证，属增量变更。

## 替代方案

- **Electron**：生态更熟，但需要再打包一份 Node 运行时，且无法复用系统 Keychain 的原生进程模型；体积与内存开销更高。
- **纯浏览器 + 本地脚本启动**：功能等价但没有"一个应用"的形态，登录页连接状态与 Dock 图标等桌面体验缺失。
- **后端作为独立安装项**：用户需要自己管理 Java 与进程生命周期，首次启动失败率高。

## 后果与回滚

- 得到单 DMG 双击即用的单机形态，完整栈叙事（多租户、RAG、可靠消息）仍由 Compose 环境承载；文档必须明确桌面版降级边界，避免把 LocalOutbox 说成 RocketMQ 链路。
- 内嵌 JVM 使 DMG 体积显著增大（jlink 全模块运行时 + Spring Boot fat jar），可接受。
- 8080 端口被其他服务占用且健康检查恰好通过时存在误连风险；当前以"端口健康即复用"为已知限制记录在案。
- 回滚点：桌面客户端完全独立于后端主链路，删除 `frontend/src-tauri`、`script/build_desktop_backend.sh` 与 `application-desktop.yml` 即回到纯 Web 交付，不影响既有测试与契约。
