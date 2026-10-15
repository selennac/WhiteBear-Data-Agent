import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from openai import APITimeoutError
from pydantic import SecretStr
from test_analysis_graph import initial_run, result, schema
from test_result_presentation import grouped

from app.agent.graph import run_graph
from app.core.config import Settings
from app.llm.query import ModelError
from app.llm.summary import generate_summary, summary_context
from app.schemas.analysis import QueryDraft, ResultSummary, SummaryNarrative
from app.services.streaming import RunManager


def test_summary_sends_bounded_samples_exact_statistics_and_no_credentials() -> None:
    rows = [[f"label-{i}", str(i) + ".01"] for i in range(100)]
    query_result = grouped(rows, truncated=True)
    settings = Settings(
        _env_file=None,
        deepseek_api_key=SecretStr("private-key"),
        app_database_url=SecretStr("postgresql+psycopg://a:private-password@host/app"),
    )
    draft = QueryDraft(action="query", sql="SELECT secret_sql", time_range="最近30天")
    with patch("app.llm.summary.ChatDeepSeek") as model:
        invoke = AsyncMock(
            return_value={
                "parsed": SummaryNarrative(text="已返回100行，结果已截断。"),
                "raw": SimpleNamespace(usage_metadata={"input_tokens": 42}),
            }
        )
        model.return_value.with_structured_output.return_value.ainvoke = invoke
        summary, usage = asyncio.run(generate_summary(settings, draft, query_result, schema()))
    context = json.loads(invoke.call_args.args[0][1].content)
    assert len(context["result_sample"]) == 20
    assert context["returned_row_statistics"][0]["returned_values_sum"] == "4951.00"
    assert context["truncated"] is True and context["returned_row_count"] == 100
    assert "label-99" not in json.dumps(context)
    assert "private-key" not in json.dumps(context) and "private-password" not in json.dumps(
        context
    )
    assert "secret_sql" not in json.dumps(context) and "schema" not in context
    assert any("截断" in note for note in summary.limitations)
    assert usage == {"input_tokens": 42}
    assert model.call_args.kwargs["timeout"] == settings.llm_summary_timeout_seconds


def test_long_sample_cells_are_clipped_and_empty_result_needs_no_model() -> None:
    draft = QueryDraft(action="query", sql="SELECT 1")
    context = summary_context(draft, grouped([["x" * 5000, "1"]]), schema())
    assert len(context["result_sample"][0][0]) == 200 and context["sample_clipped"] is True
    with patch("app.llm.summary.ChatDeepSeek") as model:
        summary, usage = asyncio.run(
            generate_summary(Settings(_env_file=None), draft, grouped([]), schema())
        )
        assert "没有数据" in summary.text and usage == {}
        clipped, _ = asyncio.run(
            generate_summary(Settings(_env_file=None), draft, grouped([], truncated=True), schema())
        )
        assert "截断" in clipped.text and "没有数据" not in clipped.text
    model.assert_not_called()


@pytest.mark.parametrize("invalid", [False, True])
def test_summary_failures_are_sanitized(invalid: bool) -> None:
    with patch("app.llm.summary.ChatDeepSeek") as model:
        model.return_value.with_structured_output.return_value.ainvoke = AsyncMock(
            return_value={"parsed": None},
            side_effect=None
            if invalid
            else APITimeoutError(request=httpx.Request("POST", "https://example.invalid/private")),
        )
        with pytest.raises(ModelError) as error:
            asyncio.run(
                generate_summary(
                    Settings(_env_file=None, deepseek_api_key=SecretStr("private")),
                    QueryDraft(action="query", sql="SELECT 1"),
                    result(),
                    schema(),
                )
            )
        assert error.value.code == ("summary_output_invalid" if invalid else "summary_timeout")
        assert "private" not in str(error.value)


def test_summary_failure_keeps_query_and_chart_without_sql_retry() -> None:
    run = initial_run()
    with (
        patch("app.agent.graph.get_schema", return_value=schema()),
        patch(
            "app.agent.graph.generate_draft",
            return_value=(QueryDraft(action="query", sql="SELECT 1"), {"input_tokens": 10}),
        ) as query,
        patch("app.agent.graph.execute_query", return_value=grouped([["A", "10.01"]])),
        patch(
            "app.agent.graph.generate_summary",
            side_effect=ModelError("summary_timeout", "总结超过 90 秒，查询结果已保留。"),
        ) as summary,
    ):
        asyncio.run(run_graph(Settings(_env_file=None), run))
    assert run.status == "succeeded" and run.result.rows == [["A", "10.01"]]
    assert run.chart.type == "bar" and run.summary is None and "保留" in run.summary_error
    assert run.steps[-1].status == "failed" and run.error_code == ""
    assert query.call_count == 1 and summary.call_count == 1


def test_summary_usage_accumulates_and_legacy_payload_gets_defaults() -> None:
    run = initial_run()
    with (
        patch("app.agent.graph.get_schema", return_value=schema()),
        patch(
            "app.agent.graph.generate_draft",
            return_value=(QueryDraft(action="query", sql="SELECT 1"), {"input_tokens": 10}),
        ),
        patch("app.agent.graph.execute_query", return_value=result()),
        patch(
            "app.agent.graph.generate_summary",
            return_value=(ResultSummary(text="订单数为12。"), {"input_tokens": 5}),
        ),
    ):
        asyncio.run(run_graph(Settings(_env_file=None), run))
    assert run.token_usage["input_tokens"] == 15 and run.summary.text == "订单数为12。"
    payload = initial_run().model_dump(
        mode="json",
        exclude={"summary", "chart", "summary_error", "chart_message", "summary_prompt_version"},
    )
    legacy = type(run).model_validate(payload)
    assert legacy.summary is None and legacy.chart is None and legacy.summary_error == ""


def test_stop_during_summary_closes_call_and_preserves_completed_query() -> None:
    async def scenario() -> None:
        entered, closed = asyncio.Event(), asyncio.Event()
        saved = []

        async def slow_summary(*args):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                closed.set()

        manager = RunManager()
        with (
            patch("app.services.streaming.create_run"),
            patch(
                "app.services.analysis.save_run",
                side_effect=lambda _, run: saved.append(run.model_copy(deep=True)),
            ),
            patch("app.agent.graph.get_schema", return_value=schema()),
            patch(
                "app.agent.graph.generate_draft",
                return_value=(QueryDraft(action="query", sql="SELECT 1"), {}),
            ),
            patch("app.agent.graph.execute_query", return_value=grouped([["A", "10.01"]])),
            patch("app.agent.graph.generate_summary", side_effect=slow_summary),
        ):
            active = await manager.start(
                Settings(_env_file=None, deepseek_api_key=SecretStr("stub")),
                initial_run().conversation_id,
                "分类销售额",
            )
            await asyncio.wait_for(entered.wait(), 2)
            await asyncio.wait_for(manager.stop(active), 2)
        assert closed.is_set() and len(saved) == 1 and not manager.active
        assert saved[0].status == "succeeded" and saved[0].result.rows == [["A", "10.01"]]
        assert saved[0].chart.type == "bar" and "已停止" in saved[0].summary_error
        assert saved[0].steps[-1].status == "cancelled"

    asyncio.run(scenario())
