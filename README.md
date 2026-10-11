# WhiteBearDataAgent

面向学习与开源展示的本地 TextToSQL 工作台。使用 FastAPI、LangGraph 和 Vue 3，逐步建立自然语言提问、SQL 校验、只读查询、图表展示与多轮分析的完整流程。

A local TextToSQL workspace for learning and open-source demos, built with FastAPI, LangGraph, PostgreSQL, and Vue 3.

## 当前状态

当前已完成可运行的工程基础和数据准备流程：

- FastAPI 应用、环境配置、健康检查、OpenAPI 文档和配置状态 CLI。
- Vue 3 + TypeScript + Vite 页面、Pinia 状态、自定义按钮和 CSS 设计变量。
- 开发 API 代理、前端构建后的 FastAPI 同域托管。
- Alembic 迁移环境、后端模块边界、业务数据与评测目录。
- Ruff、mypy、pytest、ESLint、Prettier、Vitest 和 GitHub Actions。
- 数据库初始化 CLI：独立应用库、业务库、受限访问账号、应用迁移和 LangGraph checkpoint。
- 可复现电商业务数据：六张业务表、近期订单、金额及退款约束、受控重置。
- 数据源结构接口、应用内业务说明持久化、版本化指标口径 YAML。
- 前端数据结构页：字段、关联关系、业务说明编辑和生成数据覆盖范围。

Agent 查询、会话、SSE 和图表功能尚未实现。健康检查和配置引导页无需 PostgreSQL 或 Qwen API Key 即可启动；浏览结构需要初始化 PostgreSQL，整个数据准备流程无需模型 Key。健康检查只表示后端进程可响应，不代表数据库或模型已连接。

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

后端固定从 `backend/.env` 读取配置，示例配置包含应用库、业务只读库和 Qwen 设置。连接串及 API Key 使用 `SecretStr` 保存；请勿提交 `.env`，也不要将数据库连接串或 Key 放到 `VITE_*` 前端变量中。

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

`db init` 可重复执行，不删除已有数据。它拒绝接管属于其他账号的数据库或未标记为本项目管理的同名业务 Schema；创建 `datasource_metadata` 应用表、checkpoint 表，以及 `whitebear_business` Schema 中的六张业务表和一张生成摘要表。会话与运行记录表随下一阶段功能添加。

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

Linux/macOS 使用 `export WHITEBEAR_TEST_ADMIN_URL='...'`。当前测试验证数据时间与金额约束、可复现性、初始化重复执行、只读权限、说明持久化及重置范围，无需真实模型。

## 依赖管理

后端的 `pyproject.toml` 保留项目元数据、直接依赖和工具配置；`requirements.txt` 列出运行所需的直接依赖，`requirements-dev.txt` 在此基础上添加开发工具。包依赖均不指定版本，由 pip 解析最新兼容版本和间接依赖。在 `backend/` 运行 `python -m pip install --upgrade -r requirements.txt` 可仅安装运行依赖，开发时使用 `python -m pip install --upgrade -r requirements-dev.txt`。安装会同时以可编辑模式注册本地项目。`--upgrade` 会更新环境中已经安装的直接依赖；需要更新全部间接依赖时，再加上 `--upgrade-strategy eager`。

添加或移除后端依赖时，同步更新 `pyproject.toml` 和对应的 requirements 文件。升级时重新执行上述带 `--upgrade` 的安装命令，再在虚拟环境中运行 `python -m pip check` 及开发检查。

前端初次安装和 CI 使用 `npm ci`，严格按照 `package-lock.json` 安装。添加或升级依赖时使用 `npm install`，并提交更新后的 `package.json` 和 `package-lock.json`。

## 许可证

[MIT](LICENSE)
