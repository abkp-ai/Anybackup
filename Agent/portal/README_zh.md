[中文](README_zh.md) | [English](README.md)

# AnyBackup Agent Portal 前端

`portal` 是 AnyBackup Agent 的 Web 前端工作区。  
该仓库聚焦 Agent 场景下的会话工作台与相关运维交互界面。

## 定位说明

- **它是什么**：Agent 门户前端实现。
- **面向人群**：使用会话驱动流程的运维人员与开发者。
- **它不是什么**：不是完整 AnyBackup 平台仓库，也不是独立产品仓库。

## 开源范围

当前已开放能力：

- 会话工作台 UI（聊天面板、会话列表、交互流程）
- 结构化富内容渲染（包含 AG-UI layout-tree 渲染路径）
- 前端 service 层、状态管理与本地开发工具链
- 聊天/store/service 关键路径单元测试

## 开源计划

后续将逐步开放与完善：

- 多模态卡片与 action 处理器的扩展能力
- 更清晰的 API 契约示例与本地 mock 说明
- 更稳定的测试基线（组件级 + 集成级）
- 持续清理历史占位路由并收敛到真实页面

## 快速开始

推荐环境：

```bash
Node.js 20.x
npm 10.x
```

安装并启动：

```bash
npm install
npm run dev
```

构建与测试：

```bash
npm run build
npm run test
```

## 开发配置

本地联调后端代理时，在 `.env.local` 中配置：

```bash
VITE_AUTH_SERVICE_PROXY_TARGET=http://<auth-service-host>
VITE_CONVERSATION_SERVICE_PROXY_TARGET=http://<conversation-service-host>
```

对应代理路径：

- `/api/auth_service`
- `/api/conversation_service`

## 仓库结构

```text
src/
|-- app/          # 应用装配与路由
|-- pages/        # 路由页面
|-- components/   # 可复用 UI/业务组件
|-- services/     # API 适配与协议解析
|-- store/        # Zustand 状态与会话流
|-- config/       # 应用配置
|-- test/         # 测试 setup 与辅助
`-- ...
```

## 文档入口

- 从 `AGENTS.md` 开始
- 工程规范与架构文档统一在 `docs/` 目录
- 详细实现细节下沉在文档中，不放在本 README 顶层

## 关联项目

- [Anybackup](https://github.com/anybackup-ai/Anybackup)：基于该生态构建的完整 AI 原生数据韧性平台

## 许可证

本项目遵循 [LICENSE](LICENSE) 中约定的开源许可证。

