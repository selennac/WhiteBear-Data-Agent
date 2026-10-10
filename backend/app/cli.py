"""Local management CLI; database and demo commands will be added here."""

import argparse
import json

from app import __version__
from app.core.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="WhiteBearDataAgent 本地管理工具")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("info", help="查看项目版本和配置状态（不输出凭据）")
    args = parser.parse_args()

    if args.command == "info":
        settings = Settings()
        print(
            json.dumps(
                {
                    "app_name": settings.app_name,
                    "version": __version__,
                    "environment": settings.app_env,
                    "timezone": settings.timezone,
                    "app_database_configured": settings.app_database_url is not None,
                    "business_database_configured": settings.business_database_url is not None,
                    "model_configured": settings.qwen_api_key is not None,
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
