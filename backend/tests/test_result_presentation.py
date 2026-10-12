from decimal import Decimal

import pytest

from app.schemas.analysis import QueryColumn, QueryDraft, QueryResult
from app.services.presentation import build_chart, result_statistics


def grouped(rows: list, types: list[str] | None = None, truncated: bool = False) -> QueryResult:
    types = types or ["text", "numeric"]
    return QueryResult(
        columns=[QueryColumn(name=f"column_{i}", data_type=t) for i, t in enumerate(types)],
        rows=rows,
        row_count=len(rows),
        truncated=truncated,
        elapsed_ms=1,
    )


def draft(intent: str = "auto") -> QueryDraft:
    return QueryDraft(action="query", sql="SELECT 1", chart_intent=intent)


def test_chart_selection_and_column_positions_preserve_duplicate_aliases() -> None:
    result = grouped([["2026-10-10", "123.45"], ["2026-10-11", "222.00"]], ["date", "numeric"])
    for col in result.columns:
        col.name = "same_alias"
    spec, note = build_chart(result, draft())
    assert spec.type == "line" and spec.supported_types == ["line", "bar"]
    assert spec.x_column == 0 and spec.y_columns == [1] and note == ""
    assert result.rows[0][1] == "123.45"
    assert build_chart(grouped([["华东", "120.00"]]), draft())[0].type == "bar"


@pytest.mark.parametrize(
    "rows,truncated,allowed",
    [
        ([["A", "1.10"], ["B", "2.20"]], False, True),
        ([["A", "1.10"], ["B", "2.20"]], True, False),
        ([[str(i), "1"] for i in range(9)], False, False),
        ([["A", "-1"], ["B", "2"]], False, False),
        ([["A", None], ["B", "2"]], False, False),
        ([["A", "0"], ["B", "0"]], False, False),
    ],
)
def test_pie_requires_complete_small_nonnegative_share_result(rows, truncated, allowed) -> None:
    spec, _ = build_chart(grouped(rows, truncated=truncated), draft("pie"))
    assert (spec.type == "pie") == allowed
    assert ("pie" in spec.supported_types) == allowed
    assert "pie" not in build_chart(grouped(rows, truncated=truncated), draft())[0].supported_types


def test_time_and_category_series_are_bounded_and_duplicate_groups_rejected() -> None:
    spec, _ = build_chart(
        grouped(
            [["2026-10-10", "华东", "12"], ["2026-10-10", "华南", "24"]],
            ["date", "text", "numeric"],
        ),
        draft(),
    )
    assert spec.series_column == 1 and spec.y_columns == [2]
    assert build_chart(grouped([["A", "1"], ["A", "2"]]), draft())[0] is None
    assert build_chart(grouped([["A", "NaN"]]), draft())[0] is None
    assert build_chart(grouped([["A", "9007199254740992"]]), draft())[0] is None
    assert build_chart(grouped([[str(i), "1"] for i in range(101)]), draft())[0] is None
    assert build_chart(grouped([]), draft())[0] is None
    assert build_chart(grouped([["A", "1"]]), draft("table"))[0] is None


def test_statistics_use_exact_decimals_and_describe_returned_cells() -> None:
    result = grouped(
        [["A", "123456789012345678901234567890.12"], ["B", "0.01"], ["C", None], ["D", "NaN"]],
        truncated=True,
    )
    item = result_statistics(result)[0]
    assert item["returned_values_sum"] == "123456789012345678901234567890.13"
    assert Decimal(item["min"]) == Decimal("0.01")
    assert item["null_count"] == 1 and item["invalid_count"] == 1
    assert item["numeric_count"] == 2


def test_missing_time_dimension_is_not_drawn_as_a_continuous_trend() -> None:
    spec, note = build_chart(
        grouped([["2026-10-11", "1.01"], [None, "2.02"]], ["date", "numeric"]), draft()
    )
    assert spec.type == "bar" and spec.supported_types == ["bar"]
    assert "空值" in note
