from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DatasourceSummary(BaseModel):
    id: str
    name: str
    dialect: Literal["postgresql"] = "postgresql"
    configured: bool
    schema_name: str


class ColumnSchema(BaseModel):
    name: str
    data_type: str
    nullable: bool
    primary_key: bool
    description: str = ""


class RelationshipSchema(BaseModel):
    columns: list[str]
    referred_schema: str
    referred_table: str
    referred_columns: list[str]


class TableSchema(BaseModel):
    name: str
    description: str = ""
    columns: list[ColumnSchema]
    relationships: list[RelationshipSchema]


class MetricDefinition(BaseModel):
    id: str
    label: str
    description: str
    expression: str
    time_column: str
    grain: str
    aliases: list[str]


class MetricsDocument(BaseModel):
    version: str
    default_time_range_days: int
    metrics: list[MetricDefinition]


class DatasetSummary(BaseModel):
    version: int
    generated_at: datetime
    as_of: datetime
    coverage_start: datetime
    coverage_end: datetime
    days: int
    orders: int
    seed: int
    row_counts: dict[str, int]
    recent_30_days_paid_orders: int
    recent_30_days_sales: str


class DatasourceSchema(BaseModel):
    datasource_id: str
    schema_name: str
    schema_version: str
    synced_at: datetime | None = None
    tables: list[TableSchema]
    metrics: MetricsDocument
    dataset: DatasetSummary | None = None


class MetadataPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tables: dict[str, str] = Field(default_factory=dict, max_length=6)
    columns: dict[str, dict[str, str]] = Field(default_factory=dict, max_length=6)
