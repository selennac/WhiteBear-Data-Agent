# 项目结构与模块边界

本结构遵循 [项目设计](project-design.md)。目前包含工程基础、数据库初始化、动态业务数据、结构浏览与单轮问数闭环。查询实现详见 [查询流程与接口](query-workflow.md)。

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
| `app/business` | 业务数据生成，供 CLI 调用 |
| `migrations` | 应用模型迁移；checkpoint 初始化独立管理 |

路由保持薄层，Agent 节点复用服务。业务库的只读访问与应用库的写入使用独立连接。数据库、模型连接按实际用例创建，不在模块导入或基础健康检查时连接外部服务。

当前 API 包含 `GET /api/v1/health`、数据源列表、结构读取、同步和业务说明修改；`/docs`、`/redoc` 和 `/openapi.json` 由 FastAPI 提供。会话创建、历史列表、独立问题提交和运行记录查询接口已注册；原有 JSON 接口保留，流式提交及取消接口已接入；应用生命周期管理运行任务及退出清理。结构访问只读扫描六张允许的电商业务表，应用侧 `datasource_metadata` 保存快照和说明，业务库注释不被修改。

`app/db/initialize.py` 通过独立管理连接创建数据库与账号，随后迁移应用模型、初始化 checkpoint，并由业务属主账号创建标记过的 `whitebear_business` Schema。`app/business/generator.py` 是无需数据库的纯生成器；`storage.py` 使用事务和 advisory lock 保护生成与受控重置。

## 前端

| 目录 | 职责 |
|---|---|
| `src/components/ui` | 项目自己的按钮、输入、标签页等基础组件 |
| `src/views` | 页面布局与功能组合 |
| `src/stores` | Pinia 共享状态与异步操作 |
| `src/services` | `fetch` API 客户端、SSE 分片解析与停止请求 |
| `src/types` | 前端 API 契约，由 OpenAPI 生成 |
| `src/styles` | 颜色、间距、圆角变量和全局基础样式 |

复杂交互使用 Reka UI，图标使用 Lucide，图表使用 vue-echarts。它们已声明为依赖，后续按功能按需接入。当前问数页提供问题输入、历史会话、SQL、结果表格、排序分页及实时执行记录、停止分析与断线恢复；结构页展示表、字段、外键、业务口径和数据覆盖范围，并提供业务说明编辑、加载和错误状态。`schema.generated.ts` 由 `scripts/generate_api_types.py` 从 OpenAPI 生成。

## 数据、评测与测试

- `business/metrics`：保存版本化电商 YAML 业务口径。
- `business/generated`：本地生成产物，Git 默认忽略。
- `evals/cases`：后续保存固定问数案例及参考结果。
- `evals/reports`：本地评测报告，Git 默认忽略。
- `backend/tests`：后端测试；集成测试放在 `integration`。
- 前端单元测试与被测模块相邻，使用 `*.test.ts`。
- `tests/e2e`：后续完整问数流程的 Playwright 测试。

当前 CI 验证静态检查、数据生成单元测试、原生 PostgreSQL 行为的集成测试、前端状态测试、类型一致性和构建。数据库集成测试使用独立的 `WHITEBEAR_TEST_ADMIN_URL`，创建并清理临时库及账号；查询执行、结果约束和历史恢复已有集成测试；真实模型评测需手动运行。
