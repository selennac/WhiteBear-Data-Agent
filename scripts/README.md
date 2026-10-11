# 开发辅助脚本

本目录用于后续添加 OpenAPI 类型生成、开发环境检查等辅助脚本。

激活后端虚拟环境后，应用管理命令统一使用 `python -m app.cli`；当前可用子命令为 `info`。数据库初始化与业务数据生成将通过这一入口接入。
# OpenAPI 类型生成

在项目根目录使用后端虚拟环境的 Python 运行 `python scripts/generate_api_types.py`，从 FastAPI OpenAPI 更新 `frontend/src/types/schema.generated.ts`；`--check` 验证已提交契约与后端一致。生成过程不连接数据库或模型。
