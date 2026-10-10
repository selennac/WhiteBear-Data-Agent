# 项目结构与模块边界

本结构遵循 [项目设计](project-design.md)。此次初始化提供可运行的前后端骨架，目录中的空包用于确定后续功能的归属。

后端使用 `venv + pip`，通过不指定版本的 `requirements.txt` 和 `requirements-dev.txt` 安装运行、开发依赖，使用 `pip install --upgrade` 更新到最新兼容版本；`pyproject.toml` 保留项目元数据与工具配置，包依赖同样不限制版本。前端使用 npm，通过 `package-lock.json` 固定依赖，初次安装和 CI 执行 `npm ci`。

## 后端

| 模块 | 职责 |
|---|---|
| `app/api/v1/endpoints` | 解析请求、调用服务、组织 HTTP/SSE 响应 |
| `app/schemas` | API 与 Agent 使用的 Pydantic 契约 |
| `app/core` | 配置、公共错误、日志等基础设施 |
| `app/services` | 会话、分析和元数据等应用用例 |
| `app/agent` | 图状态、路由与 LangGraph 编排 |
| `app/agent/nodes` | 调用服务完成上下文加载、生成、校验、执行、总结 |
| `app/datasources` | 业务库结构发现、SQLGlot 校验、只读查询 |
| `app/llm` | Qwen/LangChain 适配和结构化输出 |
| `app/db` | 应用库连接、SQLAlchemy Base 与模型 |
| `app/repositories` | 应用数据持久化，供服务调用 |
| `app/demo` | 示例业务数据生成，供 CLI 调用 |
| `migrations` | 应用模型迁移；checkpoint 初始化独立管理 |

路由保持薄层，Agent 节点复用服务。业务库的只读访问与应用库的写入使用独立连接。数据库、模型连接按实际用例创建，不在模块导入或基础健康检查时连接外部服务。

当前唯一业务 API 路由是 `GET /api/v1/health`；`/docs`、`/redoc` 和 `/openapi.json` 由 FastAPI 提供。初始化阶段不注册未实现的查询或数据源接口。

## 前端

| 目录 | 职责 |
|---|---|
| `src/components/ui` | 项目自己的按钮、输入、标签页等基础组件 |
| `src/views` | 页面布局与功能组合 |
| `src/stores` | Pinia 共享状态与异步操作 |
| `src/services` | `fetch` API 客户端，后续扩展 SSE 读取与取消 |
| `src/types` | 前端 API 契约，后续由 OpenAPI 生成 |
| `src/styles` | 颜色、间距、圆角变量和全局基础样式 |

复杂交互使用 Reka UI，图标使用 Lucide，图表使用 vue-echarts。它们已声明为依赖，后续按功能按需接入。当前仅实现欢迎页面与后端连接状态。

## 数据、评测与测试

- `demo/metrics`：后续保存版本化 YAML 业务口径。
- `demo/generated`：本地生成产物，Git 默认忽略。
- `evals/cases`：后续保存固定问数案例及参考结果。
- `evals/reports`：本地评测报告，Git 默认忽略。
- `backend/tests`：后端测试；集成测试放在 `integration`。
- 前端单元测试与被测模块相邻，使用 `*.test.ts`。
- `tests/e2e`：后续完整问数流程的 Playwright 测试。

当前 CI 验证静态检查、骨架测试和前端构建。数据库初始化、示例数据、查询执行和真实模型评测应在实现对应功能时补充验证。
