from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.datasources.execution import execute_query, serialize_cell
from app.datasources.validation import SQLValidationError
from app.schemas.datasource import DatasourceSchema, MetricsDocument


def test_executor_rejects_sql_before_connecting() -> None:
    schema = DatasourceSchema(
        datasource_id="business",
        schema_name="whitebear_business",
        schema_version="test",
        tables=[],
        metrics=MetricsDocument(version="1", default_time_range_days=30, metrics=[]),
    )
    with patch("app.datasources.execution.psycopg.connect") as connect:
        with pytest.raises(SQLValidationError):
            execute_query(Settings(_env_file=None), "SELECT pg_sleep(1)", schema)
    connect.assert_not_called()


def test_numeric_precision_and_datetime_serialization() -> None:
    assert serialize_cell(Decimal("12345678901234567890.01")) == "12345678901234567890.01"
    stamp = "2026-10-11T12:00:00+08:00"
    assert serialize_cell(datetime.fromisoformat(stamp)) == stamp
    assert serialize_cell(float("inf")) == "inf"
    assert serialize_cell(None) is None
