"""Bounded reads in a short-lived, read-only PostgreSQL transaction."""

import json
import math
from datetime import date, datetime, time
from decimal import Decimal
from time import perf_counter
from typing import Any

import psycopg

from app.core.config import Settings
from app.datasources.validation import validate_sql
from app.db.connections import connection_string, parse_url
from app.schemas.analysis import Cell, QueryColumn, QueryResult
from app.schemas.datasource import DatasourceSchema

MAX_ROWS = 1000
MAX_RESULT_BYTES = 2_000_000


class QueryExecutionError(ValueError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def serialize_cell(value: Any) -> Cell:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return str(value)


def execute_query(settings: Settings, sql: str, schema: DatasourceSchema) -> QueryResult:
    # Validate again at the execution boundary, including when called outside the Agent.
    validated = validate_sql(sql, schema)
    url = parse_url(settings.business_readonly_database_url, "BUSINESS_READONLY_DATABASE_URL")
    start = perf_counter()
    try:
        with psycopg.connect(connection_string(url), connect_timeout=5) as connection:
            connection.execute("SET TRANSACTION READ ONLY")
            connection.execute("SET LOCAL statement_timeout = '10s'")
            connection.execute("SET LOCAL lock_timeout = '2s'")
            connection.execute("SET LOCAL search_path = pg_catalog")
            connection.execute("SET LOCAL TIME ZONE 'Asia/Shanghai'")
            # A server cursor and outer LIMIT bound both network transfer and client memory.
            with connection.cursor(name="whitebear_result") as cursor:
                cursor.execute(f"SELECT * FROM ({validated}) AS whitebear_result LIMIT 1001")
                columns = [
                    QueryColumn(
                        name=column.name,
                        data_type=connection.adapters.types[column.type_code].name,
                    )
                    for column in cursor.description or []
                ]
                rows: list[list[Cell]] = []
                size = 0
                truncated = False
                for raw in cursor:
                    if len(rows) == MAX_ROWS:
                        truncated = True
                        break
                    row = [serialize_cell(value) for value in raw]
                    size += len(json.dumps(row, ensure_ascii=False).encode("utf-8"))
                    if size > MAX_RESULT_BYTES:
                        truncated = True
                        break
                    rows.append(row)
    except psycopg.Error as error:
        code = error.sqlstate or ""
        if code == "57014":
            raise QueryExecutionError("query_timeout", "查询超过 10 秒，请缩小范围。") from None
        if code == "55P03":
            raise QueryExecutionError("lock_timeout", "查询等待锁超时，请稍后重试。") from None
        if code in {"42601", "42703", "42803", "42883", "42P01", "22012", "22007", "22008"}:
            raise QueryExecutionError(
                "query_error",
                f"查询未通过数据库执行（PostgreSQL {code}），请检查语法、字段和数据类型。",
                retryable=True,
            ) from None
        raise QueryExecutionError(
            "database_unavailable", "业务数据库暂不可用，请检查连接和只读权限。"
        ) from None
    return QueryResult(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        truncated=truncated,
        elapsed_ms=round((perf_counter() - start) * 1000),
    )
