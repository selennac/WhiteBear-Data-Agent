from app.business.tables import SCHEMA
from app.core.config import Settings
from app.datasources.schema import apply_descriptions, discover_schema
from app.repositories.datasource import read_descriptions, save_metadata
from app.schemas.datasource import DatasourceSchema, DatasourceSummary, MetadataPatch


class InvalidMetadataError(ValueError):
    pass


def list_datasources(settings: Settings) -> list[DatasourceSummary]:
    return [
        DatasourceSummary(
            id="business",
            name="电商业务数据",
            configured=settings.business_readonly_database_url is not None,
            schema_name=SCHEMA,
        )
    ]


def get_schema(
    settings: Settings, *, sync: bool = False, patch: MetadataPatch | None = None
) -> DatasourceSchema:
    schema = discover_schema(settings)
    if patch is not None:
        known = {table.name: {column.name for column in table.columns} for table in schema.tables}
        for name, description in patch.tables.items():
            if name not in known or len(description) > 2000:
                raise InvalidMetadataError("表不存在或说明超过 2000 字。")
        for name, columns in patch.columns.items():
            if name not in known or any(
                column not in known[name] or len(description) > 2000
                for column, description in columns.items()
            ):
                raise InvalidMetadataError("字段不存在或说明超过 2000 字。")
    if sync or patch is not None:
        descriptions, schema.synced_at = save_metadata(settings, schema, patch)
    else:
        descriptions, schema.synced_at = read_descriptions(settings)
    apply_descriptions(schema, descriptions)
    return schema
