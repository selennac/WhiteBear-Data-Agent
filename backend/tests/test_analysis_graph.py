from datetime import datetime
from unittest.mock import patch
from uuid import uuid4

from app.agent.graph import run_graph
from app.core.config import Settings
from app.datasources.execution import QueryExecutionError
from app.llm.query import ModelError
from app.schemas.analysis import AnalysisRun, QueryColumn, QueryDraft, QueryResult
from app.schemas.datasource import DatasourceSchema, MetricsDocument


def initial_run() -> AnalysisRun:
    now = datetime.fromisoformat("2026-10-11T12:00:00+08:00")
    return AnalysisRun(
        id=uuid4(),
        conversation_id=uuid4(),
        question="最近30天订单数",
        created_at=now,
        reference_time=now,
        status="running",
    )


def schema() -> DatasourceSchema:
    return DatasourceSchema(
        datasource_id="business",
        schema_name="whitebear_business",
        schema_version="fixed",
        tables=[],
        metrics=MetricsDocument(version="1", default_time_range_days=30, metrics=[]),
    )


def result() -> QueryResult:
    return QueryResult(
        columns=[QueryColumn(name="orders", data_type="int8")],
        rows=[[12]],
        row_count=1,
        truncated=False,
        elapsed_ms=1,
    )


def test_execution_error_is_repaired_and_usage_accumulated() -> None:
    run = initial_run()
    with (
        patch("app.agent.graph.get_schema", return_value=schema()),
        patch(
            "app.agent.graph.generate_draft",
            side_effect=[
                (QueryDraft(action="query", sql="SELECT 1 / 0"), {"input_tokens": 10}),
                (QueryDraft(action="query", sql="SELECT 12 AS orders"), {"input_tokens": 8}),
            ],
        ) as model,
        patch(
            "app.agent.graph.execute_query",
            side_effect=[
                QueryExecutionError("query_error", "division by zero", retryable=True),
                result(),
            ],
        ),
    ):
        run_graph(Settings(_env_file=None), run)
    assert run.status == "succeeded"
    assert run.schema_version == "fixed"
    assert run.result == result()
    assert run.token_usage == {"input_tokens": 18}
    assert model.call_args.kwargs["diagnostic"] == "division by zero"
    assert len([s for s in run.steps if s.node == "generate_query"]) == 2


def test_security_violation_never_executes_or_repairs() -> None:
    run = initial_run()
    with (
        patch("app.agent.graph.get_schema", return_value=schema()),
        patch(
            "app.agent.graph.generate_draft",
            return_value=(
                QueryDraft(action="query", sql="SELECT pg_sleep(1)"),
                {},
            ),
        ) as model,
        patch("app.agent.graph.execute_query") as execute,
    ):
        run_graph(Settings(_env_file=None), run)
    assert run.error_code == "unsafe_sql"
    assert model.call_count == 1
    execute.assert_not_called()


def test_invalid_outputs_stop_after_two_repairs() -> None:
    run = initial_run()
    with (
        patch("app.agent.graph.get_schema", return_value=schema()),
        patch(
            "app.agent.graph.generate_draft", side_effect=ModelError("model_output_invalid", "bad")
        ) as model,
        patch("app.agent.graph.execute_query") as execute,
    ):
        run_graph(Settings(_env_file=None), run)
    assert run.status == "failed"
    assert model.call_count == 3
    execute.assert_not_called()


def test_clarification_and_empty_results_are_terminal() -> None:
    run = initial_run()
    with (
        patch("app.agent.graph.get_schema", return_value=schema()),
        patch(
            "app.agent.graph.generate_draft",
            return_value=(
                QueryDraft(action="clarify", clarification="销售额是否扣除退款？"),
                {},
            ),
        ),
        patch("app.agent.graph.execute_query") as execute,
    ):
        run_graph(Settings(_env_file=None), run)
    assert run.status == "clarification_required"
    execute.assert_not_called()


def test_schema_failure_stops_before_model() -> None:
    run = initial_run()
    with (
        patch("app.agent.graph.get_schema", side_effect=RuntimeError("password=secret")),
        patch("app.agent.graph.generate_draft") as model,
    ):
        run_graph(Settings(_env_file=None), run)
    assert run.status == "failed"
    assert "secret" not in run.model_dump_json()
    model.assert_not_called()
