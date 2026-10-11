import pytest
import yaml

from app.business.tables import BUSINESS_TABLES, SCHEMA
from app.core.config import PROJECT_ROOT
from app.datasources.validation import SQLValidationError, validate_sql
from app.schemas.datasource import ColumnSchema, DatasourceSchema, MetricsDocument, TableSchema


@pytest.fixture
def commerce_schema() -> DatasourceSchema:
    return DatasourceSchema(
        datasource_id="business",
        schema_name=SCHEMA,
        schema_version="test",
        tables=[
            TableSchema(
                name=table.name,
                columns=[
                    ColumnSchema(
                        name=column.name,
                        data_type=str(column.type),
                        nullable=column.nullable,
                        primary_key=column.primary_key,
                    )
                    for column in table.columns
                ],
                relationships=[],
            )
            for table in BUSINESS_TABLES
        ],
        metrics=MetricsDocument.model_validate(
            yaml.safe_load((PROJECT_ROOT / "business/metrics/commerce.yaml").read_text("utf-8"))
        ),
    )


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT COUNT(*) FROM orders",
        "SELECT o.id, SUM(i.paid_amount) FROM orders o "
        "JOIN order_items i ON i.order_id=o.id GROUP BY o.id",
        "WITH totals AS (SELECT order_id, SUM(paid_amount) AS amount "
        "FROM order_items GROUP BY order_id) "
        "SELECT o.id, t.amount FROM orders o JOIN totals t ON o.id=t.order_id",
        "SELECT id, ROW_NUMBER() OVER (ORDER BY paid_at) AS rank FROM orders",
        "SELECT DATE_TRUNC('day', paid_at), SUM(paid_amount) FROM orders GROUP BY 1",
        "SELECT COUNT(*) FROM whitebear_business.orders "
        "WHERE paid_at >= TIMESTAMPTZ '2026-10-01T00:00:00+08:00'",
        "SELECT id FROM orders UNION ALL SELECT order_id FROM order_items",
        "SELECT * FROM (SELECT id FROM orders) o",
        "SELECT SUM(paid_amount) / NULLIF(COUNT(DISTINCT order_id), 0) FROM order_items",
        "SELECT id FROM orders WHERE id IN (SELECT order_id FROM order_items)",
        "SELECT SUM(i.paid_amount), COUNT(DISTINCT o.id) FROM orders o "
        "JOIN order_items i ON o.id=i.order_id WHERE o.status='paid' "
        "AND o.paid_at >= TIMESTAMPTZ '2026-09-11T12:00:00+08:00' "
        "AND o.paid_at < TIMESTAMPTZ '2026-10-11T12:00:00+08:00'",
        "SELECT TO_CHAR(paid_at, 'YYYY-MM-DD') FROM orders WHERE id=1 OR id=2",
        "SELECT o.id FROM orders o WHERE EXISTS "
        "(SELECT 1 FROM order_items i WHERE i.order_id=o.id)",
    ],
)
def test_allowed_analytics(sql: str, commerce_schema: DatasourceSchema) -> None:
    normalized = validate_sql(sql, commerce_schema)
    assert '"whitebear_business".' in normalized
    assert validate_sql(normalized, commerce_schema) == normalized


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1; DELETE FROM orders",
        "SELECT 1; SELECT 2",
        "SELECT 1;;",
        "DELETE FROM orders",
        "UPDATE orders SET status='paid'",
        "WITH removed AS (DELETE FROM orders RETURNING id) SELECT * FROM removed",
        "SELECT * INTO copied_orders FROM orders",
        "SELECT * FROM orders FOR UPDATE",
        "SELECT * FROM pg_catalog.pg_roles",
        "SELECT * FROM public.orders",
        "SELECT * FROM whitebear_business.dataset_info",
        "SELECT * FROM otherdb.whitebear_business.orders",
        "SELECT pg_sleep(1)",
        "SELECT pg_read_file('/etc/passwd')",
        "SELECT set_config('search_path','public',false)",
        "SELECT public.sum(id) FROM orders",
        "SELECT * FROM generate_series(1, 1000000000)",
        "SELECT 'orders'::regclass",
        "SELECT * FROM orders TABLESAMPLE SYSTEM(10)",
    ],
)
def test_unsafe_sql_stops(sql: str, commerce_schema: DatasourceSchema) -> None:
    with pytest.raises(SQLValidationError) as error:
        validate_sql(sql, commerce_schema)
    assert error.value.retryable is False


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT nonexistent FROM orders",
        "SELECT o.nonexistent FROM orders o",
        "SELECT id FROM orders o JOIN order_items i ON o.id=i.order_id",
        "SELECT FROM",
    ],
)
def test_repairable_sql(sql: str, commerce_schema: DatasourceSchema) -> None:
    with pytest.raises(SQLValidationError) as error:
        validate_sql(sql, commerce_schema)
    assert error.value.retryable is True
