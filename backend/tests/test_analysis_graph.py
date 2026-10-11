import asyncio
from datetime import datetime
from unittest.mock import patch
from uuid import uuid4

from app.agent.graph import run_graph
from app.core.config import Settings
from app.datasources.execution import QueryExecutionError
from app.llm.query import ModelError
from app.schemas.analysis import (
    AnalysisRun,
    ContextTurn,
    ConversationContext,
    QueryColumn,
    QueryDraft,
    QueryResult,
)
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
        asyncio.run(run_graph(Settings(_env_file=None), run))
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
        asyncio.run(run_graph(Settings(_env_file=None), run))
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
        asyncio.run(run_graph(Settings(_env_file=None), run))
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
        asyncio.run(run_graph(Settings(_env_file=None), run))
    assert run.status == "clarification_required"
    execute.assert_not_called()


def test_schema_failure_stops_before_model() -> None:
    run = initial_run()
    with (
        patch("app.agent.graph.get_schema", side_effect=RuntimeError("password=secret")),
        patch("app.agent.graph.generate_draft") as model,
    ):
        asyncio.run(run_graph(Settings(_env_file=None), run))
    assert run.status == "failed"
    assert "secret" not in run.model_dump_json()
    model.assert_not_called()


def test_follow_up_and_repair_use_the_same_persisted_context() -> None:
    run = initial_run()
    run.input_context = ConversationContext(
        previous=ContextTurn(
            run_id=uuid4(),
            question="订单数",
            reference_time=run.reference_time,
            draft=QueryDraft(action="query", sql="SELECT 12", filters=["华东"]),
        )
    )
    draft = QueryDraft(
        action="query",
        sql="SELECT 12",
        context_mode="follow_up",
        resolved_question="华东订单数按天拆分",
        filters=["华东"],
        group_by=["支付日期"],
    )
    with (
        patch("app.agent.graph.get_schema", return_value=schema()),
        patch("app.agent.graph.generate_draft", return_value=(draft, {})) as model,
        patch(
            "app.agent.graph.execute_query",
            side_effect=[
                QueryExecutionError("query_error", "fix", retryable=True),
                result(),
            ],
        ),
    ):
        asyncio.run(run_graph(Settings(_env_file=None), run))
    assert run.status == "succeeded"
    assert model.call_count == 2
    assert all(
        call.kwargs["conversation_context"] == run.input_context for call in model.call_args_list
    )
    assert run.draft.resolved_question == "华东订单数按天拆分"


def test_model_cannot_claim_a_missing_context_source() -> None:
    run = initial_run()
    with (
        patch("app.agent.graph.get_schema", return_value=schema()),
        patch(
            "app.agent.graph.generate_draft",
            return_value=(
                QueryDraft(
                    action="query",
                    sql="SELECT 12",
                    context_mode="clarification",
                ),
                {},
            ),
        ) as model,
        patch("app.agent.graph.execute_query") as execute,
    ):
        asyncio.run(run_graph(Settings(_env_file=None), run))
    assert run.status == "failed" and run.error_code == "model_output_invalid"
    assert model.call_count == 3
    execute.assert_not_called()


def test_legacy_run_payload_still_loads() -> None:
    payload = initial_run().model_dump(mode="json")
    payload.pop("input_context")
    payload["draft"] = {"action": "query", "sql": "SELECT 12", "time_range": "最近30天"}
    run = AnalysisRun.model_validate(payload)
    assert run.input_context == ConversationContext()
    assert run.draft.filters == [] and run.draft.context_mode == "new"
