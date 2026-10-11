"""Schema descriptions live in the application database, never in the business DB."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.datasources.schema import apply_descriptions
from app.db.connections import engine_for
from app.db.models import DatasourceMetadata
from app.schemas.datasource import DatasourceSchema, MetadataPatch


def read_descriptions(settings: Settings) -> tuple[dict[str, Any], datetime | None]:
    if settings.app_database_url is None:
        return {}, None
    engine = engine_for(settings.app_database_url, "APP_DATABASE_URL")
    try:
        with Session(engine) as session:
            record = session.get(DatasourceMetadata, "business")
            return (record.descriptions, record.synced_at) if record else ({}, None)
    finally:
        engine.dispose()


def save_metadata(
    settings: Settings, schema: DatasourceSchema, patch: MetadataPatch | None = None
) -> tuple[dict[str, Any], datetime]:
    engine = engine_for(settings.app_database_url, "APP_DATABASE_URL")
    try:
        with Session(engine) as session, session.begin():
            session.execute(text("SELECT pg_advisory_xact_lock(872406102)"))
            record = session.get(DatasourceMetadata, "business")
            descriptions: dict[str, Any] = dict(record.descriptions) if record else {}
            if patch:
                descriptions["tables"] = {**descriptions.get("tables", {}), **patch.tables}
                columns = dict(descriptions.get("columns", {}))
                for name, values in patch.columns.items():
                    columns[name] = {**columns.get(name, {}), **values}
                descriptions["columns"] = columns
            synced_at = datetime.now(UTC)
            if record is None:
                record = DatasourceMetadata(datasource_id="business")
                session.add(record)
            snapshot = schema.model_copy(deep=True)
            apply_descriptions(snapshot, descriptions)
            record.snapshot = snapshot.model_dump(mode="json")
            record.schema_version = snapshot.schema_version
            record.descriptions = descriptions
            record.synced_at = synced_at
            session.flush()
            return descriptions, synced_at
    finally:
        engine.dispose()
