# WhiteBearDataAgent

面向学习与开源展示的本地 TextToSQL 工作台。使用 FastAPI、LangGraph 和 Vue 3，逐步建立自然语言提问、SQL 校验、只读查询、图表展示与多轮分析的完整流程。

A local TextToSQL workspace for learning and open-source demos, built with FastAPI, LangGraph, PostgreSQL, and Vue 3.

## 当前状态

当前已完成工程基础、数据准备和多轮问数闭环：

- FastAPI 应用、环境配置、健康检查、OpenAPI 文档和配置状态 CLI。
- Vue 3 + TypeScript + Vite 页面、Pinia 状态、自定义按钮和 CSS 设计变量。
- 开发 API 代理、前端构建后的 FastAPI 同域托管。
- Alembic 迁移环境、后端模块边界、业务数据与评测目录。
- Ruff、mypy、pytest、ESLint、Prettier、Vitest 和 GitHub Actions。
- 数据库初始化 CLI：独立应用库、业务库、受限访问账号、应用迁移和 LangGraph checkpoint。
- 可复现电商业务数据：六张业务表、近期订单、金额及退款约束、受控重置。
- 数据源结构接口、应用内业务说明持久化、版本化指标口径 YAML。
- 前端数据结构页：字段、关联关系、业务说明编辑和生成数据覆盖范围。
- DeepSeek 结构化查询生成、LangGraph 编排、SQLGlot 校验及最多两次有限纠错。
- 业务库只读查询：10 秒超时、2 秒锁等待、最多 1,000 行及 2 MB 行数据。
- 会话、消息和运行记录持久化，保存 SQL、结构版本、口径、诊断及 Token 用量。
- 前端问数工作台：历史会话、连续对话、底部输入区和独立结果区；窄屏使用抽屉浏览结果。
- 图表、表格、SQL 和执行记录标签页，快捷追问、明确追问来源及从旧结果继续分析。
- 会话删除确认，在同一事务中删除消息与运行记录，运行中的会话禁止删除。
- SSE 分析进度、停止分析、断线取消、连接清理和终态持久化。
- 多轮追问与澄清续接：从持久化历史加载最近成功方案及待澄清问题，展示完整问题、指标、筛选与分组。
- 受约束的图表配置、折线图/柱状图/饼图及本地类型切换，保存图表并恢复历史。
- 基于实际查询结果的总结、十进制统计摘要、有限样本及失败降级。

当前支持在同一会话连续追问、覆盖条件及直接回答澄清问题，并展示适合当前结果的图表和结果总结。追问语义与总结由 DeepSeek 生成，结果需结合展示口径、SQL 和原始表格核对。健康检查和配置引导无需 PostgreSQL 或 DeepSeek API Key；浏览结构需要 PostgreSQL，问数还需要应用库及模型 Key。健康检查只表示后端进程可响应，不代表数据库或模型已连接。

详细规划见 [项目设计](docs/project-design.md)，模块约定见 [项目结构](docs/project-structure.md)。

## 项目结构

```text
WhiteBearDataAgent/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/  # HTTP 请求与响应
│   │   ├── core/              # 环境配置与公共基础设施
│   │   ├── schemas/           # Pydantic 数据契约
│   │   ├── services/          # 应用服务
│   │   ├── agent/nodes/       # LangGraph 编排与节点
│   │   ├── datasources/       # Schema、SQL 校验与只读执行
│   │   ├── llm/               # 模型适配
│   │   ├── db/models/         # SQLAlchemy 应用模型
│   │   ├── repositories/      # 持久化访问
│   │   ├── business/          # 业务数据生成模块
│   │   ├── cli.py             # 本地管理入口
│   │   └── main.py            # FastAPI 入口
│   ├── migrations/            # Alembic 迁移
│   ├── tests/                 # 后端测试
│   ├── .env.example
│   ├── pyproject.toml
│   ├── requirements.txt       # 不指定版本的运行依赖
│   └── requirements-dev.txt   # 运行依赖与开发工具
├── frontend/
│   ├── src/
│   │   ├── components/ui/     # 自定义基础组件
│   │   ├── views/             # 页面
│   │   ├── stores/            # Pinia 状态
│   │   ├── services/          # API 客户端
│   │   ├── types/             # 前端契约
│   │   └── styles/            # 设计变量与全局样式
│   ├── public/
│   ├── package.json
│   └── package-lock.json
├── business/                 # 业务口径和生成数据
├── evals/                    # 固定问题与评测报告
├── tests/e2e/                # 后续端到端测试
├── scripts/                  # 开发辅助脚本
├── docs/
└── .github/workflows/ci.yml
```

## 本地启动

运行环境：Python 3.12、Node.js 22.12 或以上版本及其自带的 npm（10 或以上版本）。后端使用 Python 自带的 `venv` 和 `pip`。后续业务功能需要 PostgreSQL 16 或以上版本。

### Windows PowerShell

在项目根目录启动后端：

```powershell
Copy-Item backend/.env.example backend/.env
Set-Location backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade -r requirements-dev.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

在另一个终端，从项目根目录启动前端：

```powershell
Copy-Item frontend/.env.example frontend/.env
Set-Location frontend
npm ci
npm run dev
```

### Linux / macOS

在项目根目录启动后端：

```bash
cp backend/.env.example backend/.env
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade -r requirements-dev.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

在另一个终端，从项目根目录启动前端：

```bash
cp frontend/.env.example frontend/.env
cd frontend
npm ci
npm run dev
```

访问：

- 工作台：<http://127.0.0.1:5173>
- API 文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/api/v1/health>

前端使用相对路径 `/api/v1`，Vite 在开发时代理到后端，无需额外配置 CORS。后端地址可通过 `frontend/.env` 中的 `VITE_API_PROXY_TARGET` 调整。

### 单进程展示

先在 `frontend/` 执行 `npm run build`，再在 `backend/` 激活虚拟环境并启动 `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`。后端启动时检测 `frontend/dist/index.html`，存在时在根路径托管构建产物，可直接访问 <http://127.0.0.1:8000>。

前端构建后需要重启后端才能启用静态托管。

## 配置与管理入口

后端固定从 `backend/.env` 读取配置，示例配置包含应用库、业务只读库和 DeepSeek 设置。连接串及 API Key 使用 `SecretStr` 保存；请勿提交 `.env`，也不要将数据库连接串或 Key 放到 `VITE_*` 前端变量中。

在 `backend/` 查看当前配置状态，不输出凭据：

```bash
python -m app.cli info
```

### 初始化数据库与业务数据

安装并启动 PostgreSQL 16 或以上版本，在 `backend/.env` 配置以下四个连接串。管理账号必须已存在且具有创建数据库及角色的权限，其余三个项目账号由初始化命令创建。替换示例密码，密码包含特殊字符时使用 URL 编码：

```dotenv
ADMIN_DATABASE_URL=postgresql+psycopg://postgres:change_me_admin@127.0.0.1:5432/postgres
APP_DATABASE_URL=postgresql+psycopg://whitebear_app:change_me_app@127.0.0.1:5432/whitebear_app
BUSINESS_DATABASE_URL=postgresql+psycopg://whitebear_business_owner:change_me_owner@127.0.0.1:5432/whitebear_business
BUSINESS_READONLY_DATABASE_URL=postgresql+psycopg://whitebear_business_reader:change_me_reader@127.0.0.1:5432/whitebear_business
```

四个账号必须独立、指向同一主机和端口；管理库、应用库和业务库必须独立，业务属主和只读账号指向同一业务库。数据库及账号名使用小写英文、数字和下划线，最多 63 位。连接串使用 `postgresql+psycopg`，不支持查询参数。`ADMIN_DATABASE_URL` 和 `BUSINESS_DATABASE_URL`（业务属主）仅供 CLI 使用，HTTP 应用状态只保留运行凭据。

在 `backend/` 激活虚拟环境后执行：

```bash
python -m app.cli db init
python -m app.cli business generate --days 365 --orders 10000 --seed 42
```

`db init` 可重复执行，不删除已有数据。它拒绝接管属于其他账号的数据库或未标记为本项目管理的同名业务 Schema；创建元数据、会话、消息及运行记录应用表、checkpoint 表，以及 `whitebear_business` Schema 中的六张业务表和一张生成摘要表。已有第一阶段数据库可执行 `python -m alembic upgrade head` 升级到迁移 `0002`，保留业务数据。

生成命令默认采用上海当前时间，输出各表行数、覆盖范围及最近 30 天支付订单和销售额。支持 1 至 3650 天、2 至 100000 笔订单。固定参数可复现业务数据；真实生成时间单独记录：

```bash
python -m app.cli business generate --as-of 2026-10-08T12:00:00+08:00 --seed 42 --reset
```

已有数据时命令退出；只有显式 `--reset` 才替换数据。重置在一个事务内执行，仅删除带项目标记的业务 Schema 中七张受管表的行，不删除 Schema、表或其他数据。发生约束错误时回滚。初始化和生成完成后，在工作台点击“同步结构”查看数据并保存结构快照。编辑业务说明写入应用库，不修改业务数据库注释。

### 数据源接口

当前支持一个内置电商数据源 `business`，不返回连接凭据：

| 接口 | 功能 |
|---|---|
| `GET /api/v1/datasources` | 查看配置状态，无需连接数据库 |
| `GET /api/v1/datasources/business/schema` | 只读获取六张表、字段、关联、指标及数据摘要 |
| `POST /api/v1/datasources/business/sync` | 刷新并保存结构快照，保留已有说明 |
| `PATCH /api/v1/datasources/business/metadata` | 保存表和字段的业务说明 |

结构读取使用只读事务和超时；未配置或连接失败时返回可理解的 503 响应。结构同步和说明编辑需要已迁移的应用库。自有数据源配置接入将在后续扩展。

### 问数与多轮追问

在 `backend/.env` 配置 DeepSeek 平台的 API Key，默认模型为 `deepseek-flash`，API 地址为 `https://api.deepseek.com`：

```dotenv
DEEPSEEK_MODEL=deepseek-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_API_KEY=your_deepseek_api_key
```

查询生成和结果总结通过 `langchain-deepseek` 使用 JSON 输出，显式关闭思考模式，以配合现有响应时间和输出长度限制。可通过 `DEEPSEEK_MODEL` 改用 DeepSeek 平台支持 JSON 输出的其他模型；当前模型列表见 [DeepSeek 官方文档](https://api-docs.deepseek.com/quick_start/pricing)。配置 Key 后重启后端，在工作台“问数分析”页提交“最近 30 天的实付销售额和支付订单数”。模型获得允许的结构、业务说明和指标口径，生成 SQL 后先校验再执行。运行结果会保存，可在历史会话中重新查看。

继续输入“按品类拆分”“改成最近 7 天”可继承并修改最近成功分析的条件；需要澄清时直接填写答复，例如“用客户区域代替城市”。对话区连续展示每轮问题和总结，底部输入区标明追问来源及继承条件，Enter 发送、Shift+Enter 换行。点击“查看结果”仅切换查看对象；点击“从此结果追问”才改用该轮条件，后续成功分析或澄清自动成为新的来源。失败、取消的运行不作为继承来源；刷新或重启后可从历史会话继续。新建分析清空上下文，明确的独立新问题也会按新话题处理。

桌面宽度达到 1280px 时展示历史、对话和结果三栏；较窄屏幕使用结果抽屉，手机端也将历史折叠为抽屉。结果区切换图表、表格、SQL 和执行记录，完整口径按需展开。分析期间可以浏览已有结果、预先输入下一问，停止操作始终指向正在运行的分析。历史会话旁的删除按钮需要确认；删除该会话的全部消息与分析记录，业务数据不受影响，正在运行的会话需先完成或停止。

原有接口保留普通 JSON：`POST /api/v1/conversations` 创建会话，`GET /api/v1/conversations` 列出历史，`POST /api/v1/conversations/{id}/messages` 提交问题，`GET /api/v1/conversations/{id}` 和 `GET /api/v1/runs/{id}` 读取记录。工作台使用 `POST /api/v1/conversations/{id}/messages/stream` 接收 SSE 进度、SQL 和结果，JSON/SSE 提交均支持可选 `context_run_id` 指定同一会话内的追问来源；`POST /api/v1/runs/{id}/cancel` 等待停止、连接清理及取消状态保存；`DELETE /api/v1/conversations/{id}` 删除会话并返回 204。刷新页面或断线会取消未完成的流式分析；已完成的记录可从历史恢复。生成、执行失败返回带错误码的运行记录；未配置模型或应用库不可用返回 503。详见 [查询流程与接口](docs/query-workflow.md)。

### 图表与结果总结

查询成功后按返回列的位置生成 `ChartSpec`，保留重复列名对应的数据。时间趋势默认折线图、分类比较默认柱状图；明确占比且只有一个指标、不超过八项、无负值或空值、结果完整时使用饼图。支持时间加分类的系列，最多四个数值指标和十二个系列；复杂维度、过多分类或超出图表数值范围时保留表格并说明原因。可从下拉框切换兼容类型，复用当前结果，无需再次查询。图表浮点绘制用于查看趋势，悬浮提示保留原始数值，精确金额以表格为准。

结果总结使用独立的 DeepSeek 调用，最多提供 20 行样本、40 列和 12 KB 行样本，长文本每格最多 200 字符；服务端用十进制计算已返回行的数值统计。总结注明采样与截断限制，不把已返回行的算术和自动视为业务指标合计。总结先给总体结论，再补充关键要点（最高、最低、明显变化和数据完整性），全文不超过 300 字；超过 6 行的明细不逐行复述，交由图表和表格呈现。空结果直接给出提示，无需总结模型调用。总结调用默认最多 90 秒（`LLM_SUMMARY_TIMEOUT_SECONDS`），不自动重试；超时或失败保留成功的查询与图表。如果在查询完成后的总结阶段停止，仍保存成功查询并提示总结已停止。新字段保存在现有 JSONB 载荷中，无需数据库迁移，旧历史记录可继续读取。

### 应用模型迁移与前端类型

后续添加应用模型后，可以在 `backend/` 使用：

```bash
python -m alembic revision --autogenerate -m "describe the change"
python -m alembic upgrade head
```

迁移需要已经存在的应用数据库和有效的 `APP_DATABASE_URL`。业务表独立于应用迁移，checkpoint 由初始化 CLI 单独管理。

接口契约变更后，在项目根目录使用后端虚拟环境的 Python 生成前端类型：

```bash
python scripts/generate_api_types.py
python scripts/generate_api_types.py --check
```

## 开发检查

在 `backend/` 激活虚拟环境后：

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest
```

在 `frontend/`：

```bash
npm run lint
npm run format:check
npm test
npm run build
```

CI 执行以上检查、OpenAPI 类型一致性检查及 PostgreSQL 16 集成测试。普通本地 pytest 在未配置测试管理连接时跳过数据库集成测试；集成测试不使用项目运行配置，会创建随机名称的临时数据库和账号，结束后清理。

需要本地运行 PostgreSQL 集成测试时，显式配置已有测试管理员连接（必须使用 `postgresql+psycopg`）：

```powershell
$env:WHITEBEAR_TEST_ADMIN_URL = 'postgresql+psycopg://postgres:your_test_password@127.0.0.1:5432/postgres'
python -m pytest
```

Linux/macOS 使用 `export WHITEBEAR_TEST_ADMIN_URL='...'`。当前测试验证数据时间与金额约束、可复现性、初始化重复执行、只读权限、说明持久化、重置范围、流式进度、取消后的查询连接释放及历史恢复，无需真实模型。

## 依赖管理

后端的 `pyproject.toml` 保留项目元数据、直接依赖和工具配置；`requirements.txt` 列出运行所需的直接依赖，`requirements-dev.txt` 在此基础上添加开发工具。包依赖均不指定版本，由 pip 解析最新兼容版本和间接依赖。在 `backend/` 运行 `python -m pip install --upgrade -r requirements.txt` 可仅安装运行依赖，开发时使用 `python -m pip install --upgrade -r requirements-dev.txt`。安装会同时以可编辑模式注册本地项目。`--upgrade` 会更新环境中已经安装的直接依赖；需要更新全部间接依赖时，再加上 `--upgrade-strategy eager`。

添加或移除后端依赖时，同步更新 `pyproject.toml` 和对应的 requirements 文件。升级时重新执行上述带 `--upgrade` 的安装命令，再在虚拟环境中运行 `python -m pip check` 及开发检查。

前端初次安装和 CI 使用 `npm ci`，严格按照 `package-lock.json` 安装。添加或升级依赖时使用 `npm install`，并提交更新后的 `package.json` 和 `package-lock.json`。

## 许可证

[MIT](LICENSE)
