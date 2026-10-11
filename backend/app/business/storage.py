"""Transactional replacement with ownership checks and an advisory lock."""

from datetime import datetime
from typing import Any

from sqlalchemy import Connection, func, select, text

from app.business.generator import TIMEZONE, GenerationOptions, generate_dataset
from app.business.tables import BUSINESS_TABLES, LOCK_ID, SCHEMA, SCHEMA_MARKER, dataset_info
from app.core.config import Settings
from app.db.connections import engine_for


def require_managed_schema(connection: Connection) -> None:
    marker = connection.execute(
        text("SELECT obj_description(oid, 'pg_namespace') FROM pg_namespace WHERE nspname=:schema"),
        {"schema": SCHEMA},
    ).scalar_one_or_none()
    if marker != SCHEMA_MARKER:
        raise ValueError("业务 Schema 尚未初始化或没有项目标记；请先运行 db init。")


def store_dataset(
    settings: Settings, options: GenerationOptions, *, reset: bool = False
) -> dict[str, Any]:
    engine = engine_for(settings.business_database_url, "BUSINESS_DATABASE_URL")
    try:
        with engine.begin() as connection:
            connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": LOCK_ID})
            require_managed_schema(connection)
            occupied = any(
                connection.execute(select(func.count()).select_from(table)).scalar_one() > 0
                for table in (*BUSINESS_TABLES, dataset_info)
            )
            if occupied and not reset:
                raise ValueError("示例表已有数据；如需替换，请显式使用 --reset。")
            dataset = generate_dataset(options)
            if reset:
                # No DROP, TRUNCATE CASCADE, or deletion outside the managed table list.
                for table in (dataset_info, *reversed(BUSINESS_TABLES)):
                    connection.execute(table.delete())
            for table in BUSINESS_TABLES:
                values = dataset.rows[table.name]
                for index in range(0, len(values), 1000):
                    connection.execute(table.insert(), values[index : index + 1000])
            dataset.summary["generated_at"] = datetime.now(TIMEZONE).isoformat()
            connection.execute(dataset_info.insert().values(id=1, summary=dataset.summary))
            return dataset.summary
    finally:
        engine.dispose()
