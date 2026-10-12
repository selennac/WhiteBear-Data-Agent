"""Deterministic charts and decimal statistics over the bounded query result."""

import json
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any, Literal

from app.schemas.analysis import Cell, ChartSpec, QueryDraft, QueryResult

NUMERIC_TYPES = {
    "int2",
    "int4",
    "int8",
    "numeric",
    "decimal",
    "float4",
    "float8",
    "smallint",
    "integer",
    "bigint",
    "real",
    "double precision",
}
TIME_TYPES = {
    "date",
    "timestamp",
    "timestamptz",
    "timestamp with time zone",
    "timestamp without time zone",
}
LABEL_TYPES = TIME_TYPES | {"text", "varchar", "bpchar", "char", "character varying"}
ChartType = Literal["line", "bar", "pie"]


def decimal_value(cell: Cell) -> Decimal | None:
    if cell is None or isinstance(cell, bool):
        return None
    value = str(cell)
    if len(value) > 1000:
        return None
    try:
        number = Decimal(value)
        return number if number.is_finite() and abs(number.adjusted()) <= 1000 else None
    except InvalidOperation:
        return None


def numeric_columns(result: QueryResult) -> list[int]:
    return [
        i for i, column in enumerate(result.columns) if column.data_type.lower() in NUMERIC_TYPES
    ]


def build_chart(result: QueryResult, draft: QueryDraft) -> tuple[ChartSpec | None, str]:
    if not result.rows:
        return None, "当前结果没有可绘制的数据。"
    if draft.chart_intent == "table":
        return None, "按当前问题仅展示表格。"
    dimensions = [
        i for i, column in enumerate(result.columns) if column.data_type.lower() in LABEL_TYPES
    ]
    values = numeric_columns(result)
    if not dimensions or not values or len(dimensions) > 2 or len(values) > 4:
        return None, "当前结果不适合自动绘图，请使用一个时间或分类维度及最多四个数值指标。"
    for index in values:
        cells = [row[index] for row in result.rows]
        numbers = [decimal_value(cell) for cell in cells]
        if not any(number is not None for number in numbers) or any(
            cell is not None and (number is None or abs(number) > Decimal("9007199254740991"))
            for cell, number in zip(cells, numbers, strict=True)
        ):
            return None, "数值超出图表可表示范围或包含非有限值，请查看原始表格。"
    temporal = [i for i in dimensions if result.columns[i].data_type.lower() in TIME_TYPES]
    x = temporal[0] if temporal else dimensions[0]
    series = next((i for i in dimensions if i != x), None)
    if series is not None and (
        not temporal or result.columns[series].data_type.lower() in TIME_TYPES
    ):
        return None, "多个分类维度无法直接绘图，请保留一个分类，或使用时间和分类组合。"
    keys = [json.dumps([row[i] for i in dimensions], ensure_ascii=False) for row in result.rows]
    if len(set(keys)) != len(keys):
        return None, "分组标签存在重复，请先聚合结果后绘图。"
    categories = {str(row[x]) for row in result.rows}
    if not temporal and len(categories) > 100:
        return None, "分类超过 100 项，请缩小范围或查询排名后绘图。"
    if series is not None and len({str(row[series]) for row in result.rows}) * len(values) > 12:
        return None, "图表系列超过 12 项，请缩小分组范围。"
    supported: list[ChartType] = ["bar"]
    if temporal and all(row[x] is not None for row in result.rows):
        supported.insert(0, "line")
    share_intent = draft.chart_intent == "pie" or any(
        word in draft.resolved_question for word in ("占比", "份额", "比例")
    )
    pie_values = [decimal_value(row[values[0]]) for row in result.rows]
    if (
        share_intent
        and not temporal
        and series is None
        and len(values) == 1
        and len(result.rows) <= 8
        and not result.truncated
        and all(value is not None and value >= 0 for value in pie_values)
        and any(value is not None and value > 0 for value in pie_values)
    ):
        supported.append("pie")
    selected: ChartType = "pie" if share_intent and "pie" in supported else supported[0]
    if draft.chart_intent in supported:
        selected = next(kind for kind in supported if kind == draft.chart_intent)
    message = "图表仅展示已返回的数据，结果已截断，不能代表完整分布。" if result.truncated else ""
    if temporal and "line" not in supported:
        message = "时间分组包含空值，已使用柱状图。" + message
    if draft.chart_intent == "pie" and "pie" not in supported:
        message = "占比图需要不超过八项的完整非负数据及一个指标，已使用可用图表。" + message
    return ChartSpec(
        type=selected,
        title=(draft.resolved_question or "查询结果")[:200],
        x_column=x,
        y_columns=values,
        series_column=series,
        supported_types=supported,
    ), message


def result_statistics(result: QueryResult) -> list[dict[str, Any]]:
    statistics: list[dict[str, Any]] = []
    for index in numeric_columns(result)[:20]:
        cells = [row[index] for row in result.rows]
        numbers = [number for cell in cells if (number := decimal_value(cell)) is not None]
        item: dict[str, Any] = {
            "column_index": index,
            "name": result.columns[index].name[:120],
            "numeric_count": len(numbers),
            "null_count": cells.count(None),
            "invalid_count": sum(
                cell is not None and decimal_value(cell) is None for cell in cells
            ),
        }
        if numbers:
            # Decimal's default precision would round large monetary totals.
            precision = (
                max(number.adjusted() for number in numbers)
                - min(int(number.as_tuple().exponent) for number in numbers)
                + len(str(len(numbers)))
                + 3
            )
            with localcontext() as context:
                context.prec = max(38, precision)
                total = sum(numbers, Decimal(0))
            item.update(
                min=str(min(numbers)), max=str(max(numbers)), returned_values_sum=str(total)
            )
        statistics.append(item)
    return statistics


def result_limitations(result: QueryResult) -> list[str]:
    limitations = ["总结依据本次查询结果，不推断未查询的数据或因果关系。"]
    if result.truncated:
        limitations.append("结果已截断，统计及总结仅覆盖已返回行，不能视为全量合计或完整占比。")
    if len(result.rows) > 20:
        limitations.append("模型最多查看 20 行样本；数值统计由服务端根据全部已返回行计算。")
    return limitations
