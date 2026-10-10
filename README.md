# WhiteBearDataAgent

面向学习与开源展示的本地 TextToSQL 工作台。使用 FastAPI、LangGraph 和 Vue 3，逐步建立自然语言提问、SQL 校验、只读查询、图表展示与多轮分析的完整流程。

A local TextToSQL workspace for learning and open-source demos, built with FastAPI, LangGraph, PostgreSQL, and Vue 3.

## 当前状态

当前完成项目基础结构：

- FastAPI 应用、环境配置、健康检查、OpenAPI 文档和配置状态 CLI。
- Vue 3 + TypeScript + Vite 页面、Pinia 状态、自定义按钮和 CSS 设计变量。
- 开发 API 代理、前端构建后的 FastAPI 同域托管。
- Alembic 迁移环境、后端模块边界、示例数据与评测目录。
- Ruff、mypy、pytest、ESLint、Prettier、Vitest 和 GitHub Actions。

数据库初始化、动态示例数据生成、数据源接口、Agent 查询、会话、SSE 和图表功能尚未实现。基础服务无需 PostgreSQL 或 Qwen API Key 即可启动。健康检查只表示后端进程可响应，不代表数据库或模型已连接。

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
│   │   ├── demo/              # 示例数据生成模块
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
├── demo/                     # 业务口径和生成数据
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

Alembic 已接入应用模型元数据，当前没有业务表迁移。后续添加模型后，可以在 `backend/` 使用：

```bash
python -m alembic revision --autogenerate -m "describe the change"
python -m alembic upgrade head
```

迁移需要已经存在的应用数据库和有效的 `APP_DATABASE_URL`，连接串格式为 `postgresql+psycopg://user:password@127.0.0.1:5432/whitebear_app`。数据库、账号和 checkpoint 初始化，以及设计文档中的 `demo generate` 命令，将在后续阶段实现。

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

CI 执行以上检查。目前测试不依赖数据库或真实模型，后续随业务实现补充 PostgreSQL 集成测试和 Playwright 端到端测试。

## 依赖管理

后端的 `pyproject.toml` 保留项目元数据、直接依赖和工具配置；`requirements.txt` 列出运行所需的直接依赖，`requirements-dev.txt` 在此基础上添加开发工具。包依赖均不指定版本，由 pip 解析最新兼容版本和间接依赖。在 `backend/` 运行 `python -m pip install --upgrade -r requirements.txt` 可仅安装运行依赖，开发时使用 `python -m pip install --upgrade -r requirements-dev.txt`。安装会同时以可编辑模式注册本地项目。`--upgrade` 会更新环境中已经安装的直接依赖；需要更新全部间接依赖时，再加上 `--upgrade-strategy eager`。

添加或移除后端依赖时，同步更新 `pyproject.toml` 和对应的 requirements 文件。升级时重新执行上述带 `--upgrade` 的安装命令，再在虚拟环境中运行 `python -m pip check` 及开发检查。

前端初次安装和 CI 使用 `npm ci`，严格按照 `package-lock.json` 安装。添加或升级依赖时使用 `npm install`，并提交更新后的 `package.json` 和 `package-lock.json`。

## 许可证

[MIT](LICENSE)
