"""Integration tests only provision disposable databases via an explicit test admin URL."""

import os
import secrets
from collections.abc import Iterator

import psycopg
import pytest
from psycopg import sql
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.db.connections import connection_string
from app.db.initialize import initialize_database


@pytest.fixture(scope="session")
def database_settings() -> Iterator[Settings]:
    value = os.environ.get("WHITEBEAR_TEST_ADMIN_URL")
    if not value:
        pytest.skip("设置 WHITEBEAR_TEST_ADMIN_URL 才会运行 PostgreSQL 集成测试。")
    admin = make_url(value)
    prefix = "wb_test_" + secrets.token_hex(4)
    app_role, owner_role, reader_role = (f"{prefix}_{name}" for name in ("app", "owner", "reader"))
    app_db, business_db = f"{prefix}_app", f"{prefix}_business"
    password = secrets.token_urlsafe(24)
    config = Settings(
        _env_file=None,
        admin_database_url=value,
        app_database_url=admin.set(
            username=app_role, password=password, database=app_db
        ).render_as_string(hide_password=False),
        business_database_url=admin.set(
            username=owner_role, password=password, database=business_db
        ).render_as_string(hide_password=False),
        business_readonly_database_url=admin.set(
            username=reader_role, password=password, database=business_db
        ).render_as_string(hide_password=False),
    )
    try:
        initialize_database(config)
        yield config
    finally:
        with psycopg.connect(connection_string(admin), autocommit=True) as connection:
            for name in (app_db, business_db):
                connection.execute(
                    sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
                )
            for name in (app_role, owner_role, reader_role):
                connection.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(name)))
