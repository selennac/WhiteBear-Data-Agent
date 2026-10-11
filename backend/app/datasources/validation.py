"""Parse and resolve SQL before it can reach the restricted business connection."""

import sqlglot
from sqlglot import exp
from sqlglot.errors import OptimizeError, ParseError, TokenError
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

from app.schemas.datasource import DatasourceSchema

# Only built-in analytical functions; database search_path is pinned to pg_catalog.
ALLOWED_FUNCTIONS = frozenset(
    {
        "ABS",
        "AVG",
        "CEIL",
        "CEILING",
        "COALESCE",
        "COUNT",
        "DATE_TRUNC",
        "EXTRACT",
        "FLOOR",
        "GREATEST",
        "LEAST",
        "LOWER",
        "MAX",
        "MIN",
        "NULLIF",
        "ROUND",
        "SUM",
        "UPPER",
        "LENGTH",
        "CHAR_LENGTH",
        "CONCAT",
        "CONCAT_WS",
        "SUBSTRING",
        "TRIM",
        "ROW_NUMBER",
        "RANK",
        "DENSE_RANK",
        "LAG",
        "LEAD",
        "FIRST_VALUE",
        "LAST_VALUE",
        "NTH_VALUE",
        "NTILE",
        "PERCENT_RANK",
        "CUME_DIST",
        "STDDEV",
        "STDDEV_POP",
        "STDDEV_SAMP",
        "VARIANCE",
        "VAR_POP",
        "VAR_SAMP",
        "CAST",
        "CURRENT_DATE",
        "CURRENT_TIMESTAMP",
        "TIMESTAMP_TRUNC",
        "TO_CHAR",
        "TIME_TO_STR",
        "DATE_PART",
        "CASE",
        "IF",
        "EXISTS",
    }
)
FORBIDDEN_NODES = frozenset(
    {
        "Insert",
        "Update",
        "Delete",
        "Merge",
        "Create",
        "Drop",
        "Alter",
        "Command",
        "Copy",
        "Into",
        "Lock",
        "Transaction",
        "Set",
        "Use",
        "Grant",
        "Revoke",
        "TruncateTable",
        "Parameter",
        "Placeholder",
        "SessionParameter",
        "Collate",
        "TableSample",
    }
)
ALLOWED_CASTS = frozenset(
    {
        "TEXT",
        "VARCHAR",
        "CHAR",
        "INT",
        "BIGINT",
        "SMALLINT",
        "DECIMAL",
        "DOUBLE",
        "FLOAT",
        "BOOLEAN",
        "DATE",
        "TIMESTAMP",
        "TIMESTAMPTZ",
        "INTERVAL",
    }
)


class SQLValidationError(ValueError):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


def validate_sql(sql: str, schema: DatasourceSchema) -> str:
    if not sql.strip() or len(sql) > 20000:
        raise SQLValidationError("SQL 为空或超过长度限制。", retryable=True)
    try:
        statements = sqlglot.parse(sql, read="postgres")
    except (ParseError, TokenError):
        raise SQLValidationError("SQL 无法按 PostgreSQL 语法解析。", retryable=True) from None
    if len(statements) != 1 or statements[0] is None:
        raise SQLValidationError("仅允许执行一条只读查询。")
    query = statements[0]
    if not isinstance(query, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise SQLValidationError("仅允许 SELECT 查询。")
    for node in query.walk():
        if type(node).__name__ in FORBIDDEN_NODES:
            raise SQLValidationError("SQL 包含写操作、锁或不允许的语句。")
        if isinstance(node, exp.Func) and not isinstance(node, exp.Connector):
            name = node.name.upper() if isinstance(node, exp.Anonymous) else node.sql_name()
            if name not in ALLOWED_FUNCTIONS or isinstance(node.parent, exp.Dot):
                raise SQLValidationError("SQL 使用了不允许的函数。")
        if isinstance(node, exp.Cast):
            target = node.args.get("to")
            if (
                not isinstance(target, exp.DataType)
                or getattr(target.this, "name", target.this) not in ALLOWED_CASTS
            ):
                raise SQLValidationError("SQL 使用了不允许的类型转换。")
    allowed = {
        table.name: {column.name: column.data_type for column in table.columns}
        for table in schema.tables
    }
    # Scope resolution distinguishes actual tables from CTE names and derived subqueries.
    try:
        for scope in traverse_scope(query):
            for source in scope.sources.values():
                if not isinstance(source, exp.Table):
                    continue
                if (
                    not isinstance(source.this, exp.Identifier)
                    or source.catalog
                    or source.db not in ("", schema.schema_name)
                    or source.name not in allowed
                ):
                    raise SQLValidationError("SQL 引用了允许范围外的表或 Schema。")
                source.set("db", exp.to_identifier(schema.schema_name))
        qualified = qualify(
            query,
            dialect="postgres",
            schema={schema.schema_name: allowed} if allowed else {},
            validate_qualify_columns=True,
            quote_identifiers=True,
        )
    except OptimizeError:
        raise SQLValidationError(
            "SQL 字段或别名无法解析，请依据提供的结构修正。", retryable=True
        ) from None
    return qualified.sql(dialect="postgres", comments=False)
