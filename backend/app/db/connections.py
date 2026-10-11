"""Short-lived connections, created only when a database operation is requested."""

from typing import Any

from pydantic import SecretStr
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import URL, make_url
from sqlalchemy.pool import NullPool

from app.core.async_work import current_work


class DatabaseConfigurationError(ValueError):
    pass


def parse_url(value: SecretStr | None, name: str) -> URL:
    if value is None:
        raise DatabaseConfigurationError(f"请在 backend/.env 配置 {name}。")
    try:
        url = make_url(value.get_secret_value())
    except Exception:
        raise DatabaseConfigurationError(f"{name} 不是有效的数据库连接串。") from None
    if (
        url.drivername != "postgresql+psycopg"
        or not url.host
        or not url.database
        or not url.username
        or not url.password
        or url.query
    ):
        raise DatabaseConfigurationError(
            f"{name} 应使用 postgresql+psycopg://账号:密码@主机:端口/数据库（不含查询参数）。"
        )
    return url


def connection_string(url: URL) -> str:
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


def engine_for(value: SecretStr | None, name: str) -> Engine:
    work = current_work.get()
    if work is not None:
        work.check()
    engine = create_engine(
        parse_url(value, name),
        poolclass=NullPool,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 5,
            "options": "-c statement_timeout=10000 -c lock_timeout=2000",
        },
    )

    if work is not None:

        @event.listens_for(engine, "connect")
        def register(connection: Any, record: Any) -> None:
            work.register(connection)

        @event.listens_for(engine, "before_cursor_execute")
        def check(*args: Any) -> None:
            work.check()

    return engine
