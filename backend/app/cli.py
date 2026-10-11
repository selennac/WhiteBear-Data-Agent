"""Local management CLI for configuration, database provisioning and business generation."""

import argparse
import json
from datetime import datetime

import psycopg
from sqlalchemy.exc import SQLAlchemyError

from app import __version__
from app.business.generator import TIMEZONE, GenerationOptions
from app.business.storage import store_dataset
from app.core.config import Settings
from app.db.initialize import initialize_database


def main() -> None:
    parser = argparse.ArgumentParser(description="WhiteBearDataAgent 本地管理工具")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("info", help="查看项目版本和配置状态（不输出凭据）")
    database = commands.add_parser("db", help="数据库管理").add_subparsers(
        dest="db_command", required=True
    )
    database.add_parser("init", help="创建数据库、受限账号、应用表、checkpoint 和业务表")
    business = commands.add_parser("business", help="业务数据管理").add_subparsers(
        dest="business_command", required=True
    )
    generate = business.add_parser("generate", help="生成可复现电商数据")
    generate.add_argument("--as-of", help="带时区的 ISO 参考时间；默认上海当前时间")
    generate.add_argument("--days", type=int, default=365)
    generate.add_argument("--orders", type=int, default=10000)
    generate.add_argument("--seed", type=int, default=42)
    generate.add_argument("--reset", action="store_true", help="仅替换项目受管业务表中的数据")
    args = parser.parse_args()
    settings = Settings()

    if args.command == "info":
        print(
            json.dumps(
                {
                    "app_name": settings.app_name,
                    "version": __version__,
                    "environment": settings.app_env,
                    "timezone": settings.timezone,
                    "app_database_configured": settings.app_database_url is not None,
                    "business_database_configured": settings.business_database_url is not None,
                    "business_readonly_database_configured": (
                        settings.business_readonly_database_url is not None
                    ),
                    "model_configured": settings.qwen_api_key is not None,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        try:
            if args.command == "db":
                result = initialize_database(settings)
            else:
                as_of = datetime.fromisoformat(args.as_of) if args.as_of else datetime.now(TIMEZONE)
                result = store_dataset(
                    settings,
                    GenerationOptions(
                        as_of=as_of, days=args.days, orders=args.orders, seed=args.seed
                    ),
                    reset=args.reset,
                )
        except ValueError as error:
            parser.exit(2, f"{error}\n")
        except (psycopg.Error, SQLAlchemyError):
            parser.exit(2, "数据库操作失败；请检查连接、账号权限和初始化状态。\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
