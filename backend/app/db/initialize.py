"""Explicit CLI-only provisioning of databases, restricted roles and checkpoints."""

import asyncio
import re
import sys
from typing import Any

import psycopg
from alembic import command
from alembic.config import Config
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import URL

from app.business.storage import require_managed_schema
from app.business.tables import LOCK_ID, SCHEMA, SCHEMA_MARKER, metadata
from app.core.config import BACKEND_ROOT, Settings
from app.db.connections import (
    DatabaseConfigurationError,
    connection_string,
    engine_for,
    parse_url,
)


def provisioning_urls(settings: Settings) -> dict[str, URL]:
    urls = {
        "admin": parse_url(settings.admin_database_url, "ADMIN_DATABASE_URL"),
        "app": parse_url(settings.app_database_url, "APP_DATABASE_URL"),
        "business": parse_url(settings.business_database_url, "BUSINESS_DATABASE_URL"),
        "reader": parse_url(
            settings.business_readonly_database_url, "BUSINESS_READONLY_DATABASE_URL"
        ),
    }
    if len({(url.host, url.port or 5432) for url in urls.values()}) != 1:
        raise DatabaseConfigurationError("初始化要求四个连接串指向同一 PostgreSQL 实例。")
    if urls["business"].database != urls["reader"].database:
        raise DatabaseConfigurationError("业务属主账号与只读账号必须连接同一个业务库。")
    if len({urls[name].database for name in ("admin", "app", "business")}) != 3:
        raise DatabaseConfigurationError("管理库、应用库和业务库必须彼此独立。")
    if len({url.username for url in urls.values()}) != 4:
        raise DatabaseConfigurationError("管理、应用、业务属主和只读账号必须彼此独立。")
    for url in urls.values():
        for value in (url.username, url.database):
            if not value or not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", value):
                raise DatabaseConfigurationError(
                    "数据库与账号名应为最多 63 位的小写英文、数字、下划线。"
                )
    return urls


async def setup_checkpoints(url: URL) -> None:
    async with AsyncPostgresSaver.from_conn_string(connection_string(url)) as saver:
        await saver.setup()


def initialize_database(settings: Settings) -> dict[str, Any]:
    urls = provisioning_urls(settings)
    with psycopg.connect(
        connection_string(urls["admin"]), autocommit=True, connect_timeout=5
    ) as conn:
        if conn.info.server_version < 160000:
            raise ValueError("需要 PostgreSQL 16 或更高版本。")
        # A session lock serializes nontransactional CREATE DATABASE operations.
        conn.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
        existing_roles: set[str] = set()
        existing_databases: set[str] = set()
        # Check every target before changing any passwords or database privileges.
        for name in ("app", "business", "reader"):
            url = urls[name]
            existing = conn.execute(
                "SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls "
                "FROM pg_roles WHERE rolname = %s",
                (url.username,),
            ).fetchone()
            if existing and existing[0]:
                raise ValueError(f"账号 {url.username} 已有管理权限，不能作为项目运行账号。")
            memberships = conn.execute(
                "SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member "
                "WHERE r.rolname=%s LIMIT 1",
                (url.username,),
            ).fetchone()
            if memberships:
                raise ValueError(f"账号 {url.username} 有其他角色成员关系，请使用独立项目账号。")
            if existing:
                existing_roles.add(name)
        for name in ("app", "business"):
            url = urls[name]
            owner = conn.execute(
                "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=%s",
                (url.database,),
            ).fetchone()
            if owner and owner[0] != url.username:
                raise ValueError(f"数据库 {url.database} 已属于其他账号，初始化已停止。")
            if owner:
                existing_databases.add(name)
        for name in ("app", "business", "reader"):
            url = urls[name]
            action = "ALTER" if name in existing_roles else "CREATE"
            conn.execute(
                sql.SQL(
                    action + " ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                    "NOREPLICATION NOBYPASSRLS NOINHERIT PASSWORD {}"
                ).format(sql.Identifier(str(url.username)), sql.Literal(url.password))
            )
        for name in ("app", "business"):
            url = urls[name]
            if name not in existing_databases:
                conn.execute(
                    sql.SQL("CREATE DATABASE {} OWNER {}").format(
                        sql.Identifier(str(url.database)), sql.Identifier(str(url.username))
                    )
                )
            conn.execute(
                sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(
                    sql.Identifier(str(url.database))
                )
            )
        conn.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(str(urls["business"].database)),
                sql.Identifier(str(urls["reader"].username)),
            )
        )
        conn.execute(
            sql.SQL("ALTER ROLE {} SET default_transaction_read_only = on").format(
                sql.Identifier(str(urls["reader"].username))
            )
        )
    app_engine = engine_for(settings.app_database_url, "APP_DATABASE_URL")
    try:
        with app_engine.begin() as connection:
            connection.execute(text("REVOKE ALL ON SCHEMA public FROM PUBLIC"))
    finally:
        app_engine.dispose()
    migration = Config(str(BACKEND_ROOT / "alembic.ini"))
    migration.attributes["database_url"] = urls["app"].render_as_string(hide_password=False)
    command.upgrade(migration, "head")
    # psycopg's async driver needs the selector loop on Windows.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(setup_checkpoints(urls["app"]))
    business_engine = engine_for(settings.business_database_url, "BUSINESS_DATABASE_URL")
    try:
        with business_engine.begin() as connection:
            connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": LOCK_ID})
            connection.execute(text("REVOKE ALL ON SCHEMA public FROM PUBLIC"))
            exists = connection.execute(
                text("SELECT 1 FROM pg_namespace WHERE nspname=:schema"), {"schema": SCHEMA}
            ).scalar_one_or_none()
            if not exists:
                connection.execute(text(f"CREATE SCHEMA {SCHEMA}"))
                connection.execute(text(f"COMMENT ON SCHEMA {SCHEMA} IS '{SCHEMA_MARKER}'"))
            require_managed_schema(connection)
            connection.execute(text(f"REVOKE ALL ON SCHEMA {SCHEMA} FROM PUBLIC"))
            metadata.create_all(connection)
            # Only validated identifiers reach this fixed-schema privilege statement.
            reader = str(urls["reader"].username)
            connection.execute(text(f'REVOKE ALL ON SCHEMA {SCHEMA} FROM "{reader}"'))
            connection.execute(text(f'GRANT USAGE ON SCHEMA {SCHEMA} TO "{reader}"'))
            connection.execute(text(f'REVOKE ALL ON ALL TABLES IN SCHEMA {SCHEMA} FROM "{reader}"'))
            connection.execute(text(f'GRANT SELECT ON ALL TABLES IN SCHEMA {SCHEMA} TO "{reader}"'))
    finally:
        business_engine.dispose()
    # Verify that the configured reader can actually connect to the managed dataset.
    reader_engine = engine_for(
        settings.business_readonly_database_url, "BUSINESS_READONLY_DATABASE_URL"
    )
    try:
        with reader_engine.connect() as connection:
            require_managed_schema(connection)
            connection.execute(text(f"SELECT id FROM {SCHEMA}.dataset_info LIMIT 1"))
    finally:
        reader_engine.dispose()
    return {
        "status": "ready",
        "app_database": urls["app"].database,
        "business_database": urls["business"].database,
        "schema": SCHEMA,
        "checkpoints": "ready",
    }
