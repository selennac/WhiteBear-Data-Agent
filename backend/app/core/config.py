"""Environment configuration; basic health checks do not require external services."""

from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    app_name: str = "WhiteBearDataAgent"
    app_env: Literal["development", "test", "production"] = "development"
    timezone: str = "Asia/Shanghai"
    app_database_url: SecretStr | None = None
    business_readonly_database_url: SecretStr | None = None
    # Administrative and business-owner credentials are only used by the CLI.
    admin_database_url: SecretStr | None = None
    business_database_url: SecretStr | None = None
    qwen_model: str = "qwen3.7-plus"
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_api_key: SecretStr | None = None
    frontend_dist: Path = PROJECT_ROOT / "frontend" / "dist"
