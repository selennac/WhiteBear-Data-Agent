"""Read-only discovery restricted to the six built-in commerce tables."""

import hashlib
import json
from typing import Any

import yaml
from sqlalchemy import inspect, select, text

from app.business.storage import require_managed_schema
from app.business.tables import BUSINESS_TABLES, SCHEMA, dataset_info
from app.core.config import PROJECT_ROOT, Settings
from app.db.connections import engine_for
from app.schemas.datasource import (
    ColumnSchema,
    DatasetSummary,
    DatasourceSchema,
    MetricsDocument,
    RelationshipSchema,
    TableSchema,
)


def schema_version(tables: list[TableSchema], metrics: MetricsDocument) -> str:
    fingerprint = json.dumps(
        {"tables": [table.model_dump() for table in tables], "metrics": metrics.model_dump()},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(fingerprint.encode()).hexdigest()


def apply_descriptions(schema: DatasourceSchema, descriptions: dict[str, Any]) -> None:
    for table in schema.tables:
        table.description = descriptions.get("tables", {}).get(table.name, table.description)
        for column in table.columns:
            column.description = (
                descriptions.get("columns", {})
                .get(table.name, {})
                .get(column.name, column.description)
            )
    schema.schema_version = schema_version(schema.tables, schema.metrics)


def discover_schema(settings: Settings) -> DatasourceSchema:
    metrics = MetricsDocument.model_validate(
        yaml.safe_load((PROJECT_ROOT / "business" / "metrics" / "commerce.yaml").read_text("utf-8"))
    )
    engine = engine_for(settings.business_readonly_database_url, "BUSINESS_READONLY_DATABASE_URL")
    try:
        with engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            require_managed_schema(connection)
            inspector = inspect(connection)
            tables = []
            for table in BUSINESS_TABLES:
                primary_keys = inspector.get_pk_constraint(table.name, schema=SCHEMA)[
                    "constrained_columns"
                ]
                tables.append(
                    TableSchema(
                        name=table.name,
                        description=inspector.get_table_comment(table.name, schema=SCHEMA)["text"]
                        or "",
                        columns=[
                            ColumnSchema(
                                name=column["name"],
                                data_type=str(column["type"].compile(dialect=engine.dialect)),
                                nullable=column["nullable"],
                                primary_key=column["name"] in primary_keys,
                                description=column.get("comment") or "",
                            )
                            for column in inspector.get_columns(table.name, schema=SCHEMA)
                        ],
                        relationships=[
                            RelationshipSchema(
                                columns=key["constrained_columns"],
                                referred_schema=key["referred_schema"] or SCHEMA,
                                referred_table=key["referred_table"],
                                referred_columns=key["referred_columns"],
                            )
                            for key in inspector.get_foreign_keys(table.name, schema=SCHEMA)
                        ],
                    )
                )
            summary = connection.execute(select(dataset_info.c.summary)).scalar_one_or_none()
    finally:
        engine.dispose()
    return DatasourceSchema(
        datasource_id="business",
        schema_name=SCHEMA,
        schema_version=schema_version(tables, metrics),
        tables=tables,
        metrics=metrics,
        dataset=DatasetSummary.model_validate(summary) if summary else None,
    )
