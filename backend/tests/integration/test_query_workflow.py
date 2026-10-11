import asyncio
import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text

from app.business.generator import GenerationOptions, generate_dataset
from app.business.storage import store_dataset
from app.core.async_work import run_blocking
from app.core.config import Settings
from app.datasources.execution import QueryExecutionError, execute_query
from app.db.connections import connection_string, engine_for, parse_url
from app.main import create_app
from app.repositories.analysis import create_conversation, create_run, save_run
from app.schemas.analysis import ConversationCreate, QueryDraft
from app.services.analysis import new_run
from app.services.datasource import get_schema
from app.services.streaming import RunManager


@pytest.fixture(scope="module")
def query_settings(query_database_settings: Settings) -> Settings:
    store_dataset(
        query_database_settings,
        GenerationOptions(
            as_of=datetime.fromisoformat("2026-10-11T12:00:00+08:00"),
            orders=1500,
        ),
    )
    return query_database_settings.model_copy(update={"qwen_api_key": SecretStr("model-stub")})


def test_bounded_reads_empty_results_and_errors(query_settings: Settings) -> None:
    schema = get_schema(query_settings)
    result = execute_query(
        query_settings, "SELECT id, paid_amount, paid_at FROM orders ORDER BY id", schema
    )
    assert result.row_count == 1000
    assert result.truncated is True
    assert result.columns[0].name == "id"
    assert isinstance(result.rows[0][1], str)
    empty = execute_query(query_settings, "SELECT id FROM orders WHERE id < 0", schema)
    assert empty.rows == [] and empty.truncated is False
    with pytest.raises(QueryExecutionError) as error:
        execute_query(query_settings, "SELECT 1 / 0", schema)
    assert error.value.retryable is True
    # The previous failed transaction is closed, so subsequent reads work normally.
    assert execute_query(query_settings, "SELECT COUNT(*) FROM orders", schema).rows == [[1500]]
    with patch("app.datasources.execution.MAX_RESULT_BYTES", 10):
        bounded = execute_query(query_settings, "SELECT id FROM orders ORDER BY id", schema)
    assert bounded.truncated is True
    assert 0 < bounded.row_count < 1000


def test_query_and_lock_timeouts_close_connections(query_settings: Settings) -> None:
    schema = get_schema(query_settings)
    with pytest.raises(QueryExecutionError) as timeout:
        execute_query(
            query_settings,
            "SELECT COUNT(*) FROM orders a CROSS JOIN orders b "
            "CROSS JOIN orders c CROSS JOIN orders d",
            schema,
        )
    assert timeout.value.code == "query_timeout"
    assert timeout.value.retryable is False
    owner = engine_for(query_settings.business_database_url, "BUSINESS_DATABASE_URL")
    try:
        with owner.connect() as connection:
            connection.execute(
                text("LOCK TABLE whitebear_business.orders IN ACCESS EXCLUSIVE MODE")
            )
            with pytest.raises(QueryExecutionError) as locked:
                execute_query(query_settings, "SELECT id FROM orders", schema)
            assert locked.value.code == "lock_timeout"
            connection.rollback()
    finally:
        owner.dispose()
    assert execute_query(query_settings, "SELECT COUNT(*) FROM orders", schema).rows == [[1500]]


def test_question_to_sql_table_and_persisted_history(
    query_settings: Settings, tmp_path: Path
) -> None:
    draft = QueryDraft(
        action="query",
        metrics=["paid_sales", "paid_orders"],
        time_range="2026-09-11 12:00 至 2026-10-11 12:00（Asia/Shanghai）",
        assumptions=["实付销售额不扣减退款"],
        sql="""SELECT SUM(i.paid_amount) AS sales, COUNT(DISTINCT o.id) AS paid_orders
        FROM whitebear_business.orders o
        JOIN whitebear_business.order_items i ON i.order_id = o.id
        WHERE o.paid_at >= TIMESTAMPTZ '2026-09-11T12:00:00+08:00'
          AND o.paid_at < TIMESTAMPTZ '2026-10-11T12:00:00+08:00'""",
    )
    config = query_settings.model_copy(update={"frontend_dist": tmp_path})
    with patch("app.agent.graph.generate_draft", return_value=(draft, {"input_tokens": 100})):
        with TestClient(create_app(config)) as client:
            conversation = client.post("/api/v1/conversations", json={}).json()
            assert UUID(conversation["id"])
            response = client.post(
                f"/api/v1/conversations/{conversation['id']}/messages",
                json={"question": "2026年9月11日12点到10月11日12点的实付销售额和支付订单数"},
            )
            assert response.status_code == 200, response.text
            run = response.json()
            assert run["status"] == "succeeded", (
                run["error_code"],
                run["error_message"],
                run["steps"],
            )
            # Generator summaries include the as_of endpoint, while the query uses [start, end).
            end = datetime.fromisoformat("2026-10-11T12:00:00+08:00")
            dataset = generate_dataset(GenerationOptions(as_of=end, orders=1500))
            orders = [
                row
                for row in dataset.rows["orders"]
                if row["paid_at"] is not None and end - timedelta(days=30) <= row["paid_at"] < end
            ]
            assert run["result"]["rows"] == [
                [
                    str(sum((row["paid_amount"] for row in orders), Decimal("0.00"))),
                    len(orders),
                ]
            ]
    # A new application instance reads persisted records without invoking the model.
    with TestClient(create_app(config)) as client:
        assert client.get(f"/api/v1/runs/{run['id']}").json() == run
        detail = client.get(f"/api/v1/conversations/{conversation['id']}").json()
        assert detail["runs"] == [run]
        assert client.get("/api/v1/conversations").json()[0]["title"].startswith("2026年")


def test_unsafe_sql_and_clarification_are_saved(query_settings: Settings, tmp_path: Path) -> None:
    config = query_settings.model_copy(update={"frontend_dist": tmp_path})
    for draft, status in [
        (QueryDraft(action="query", sql="SELECT pg_sleep(1)"), "failed"),
        (
            QueryDraft(action="clarify", clarification="要按哪个时间口径统计？"),
            "clarification_required",
        ),
    ]:
        with (
            patch("app.agent.graph.generate_draft", return_value=(draft, {})),
            patch("app.agent.graph.execute_query") as execute,
            TestClient(create_app(config)) as client,
        ):
            conversation_id = client.post("/api/v1/conversations", json={}).json()["id"]
            run = client.post(
                f"/api/v1/conversations/{conversation_id}/messages",
                json={"question": "销售额"},
            ).json()
            assert run["status"] == status
            assert client.get(f"/api/v1/runs/{run['id']}").json()["status"] == status
            execute.assert_not_called()


def test_cancel_interrupts_postgres_and_closes_reader_connection(query_settings: Settings) -> None:
    async def scenario() -> None:
        schema = await run_blocking(get_schema, query_settings)
        business = parse_url(
            query_settings.business_readonly_database_url, "BUSINESS_READONLY_DATABASE_URL"
        )
        admin = parse_url(query_settings.admin_database_url, "ADMIN_DATABASE_URL")
        with psycopg.connect(connection_string(admin), autocommit=True) as probe:
            task = asyncio.create_task(
                run_blocking(
                    execute_query,
                    query_settings,
                    "SELECT COUNT(*) FROM orders a CROSS JOIN orders b "
                    "CROSS JOIN orders c CROSS JOIN orders d",
                    schema,
                )
            )

            def active_count() -> int:
                return probe.execute(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = %s AND usename = %s",
                    (business.database, business.username),
                ).fetchone()[0]

            async def wait_until_query() -> None:
                while not await asyncio.to_thread(active_count):
                    await asyncio.sleep(0.02)

            try:
                await asyncio.wait_for(wait_until_query(), 5)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.wait_for(task, 3)
                assert await asyncio.to_thread(active_count) == 0
            finally:
                if not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
        assert (
            await run_blocking(execute_query, query_settings, "SELECT COUNT(*) FROM orders", schema)
        ).rows == [[1500]]

    asyncio.run(scenario())


def test_cancel_api_persists_history_across_app_instances(
    query_settings: Settings, tmp_path: Path
) -> None:
    async def scenario() -> tuple[str, str]:
        model_entered = asyncio.Event()

        async def slow_model(*args, **kwargs):
            model_entered.set()
            await asyncio.Event().wait()

        settings = query_settings.model_copy(update={"frontend_dist": tmp_path})
        app = create_app(settings)
        manager: RunManager = app.state.runs
        conversation = await run_blocking(create_conversation, settings, ConversationCreate())
        with patch("app.agent.graph.generate_draft", side_effect=slow_model):
            active = await manager.start(settings, conversation.id, "订单数")
            await asyncio.wait_for(model_entered.wait(), 10)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(f"/api/v1/runs/{active.run.id}/cancel")
                assert response.status_code == 200, response.text
                saved = response.json()
                assert saved["status"] == "cancelled"
                assert saved["completed_at"]
                assert saved["steps"][-1]["status"] == "cancelled"
                assert (await client.post(f"/api/v1/runs/{active.run.id}/cancel")).json() == saved
            assert not manager.active
        return str(conversation.id), str(active.run.id)

    conversation_id, run_id = asyncio.run(scenario())
    with TestClient(
        create_app(query_settings.model_copy(update={"frontend_dist": tmp_path}))
    ) as client:
        assert client.get(f"/api/v1/runs/{run_id}").json()["status"] == "cancelled"
        assert (
            client.get(f"/api/v1/conversations/{conversation_id}").json()["runs"][-1]["status"]
            == "cancelled"
        )


@pytest.mark.parametrize("endpoint", ["messages", "messages/stream"])
def test_follow_up_overrides_and_clarification_survive_restart(
    query_settings: Settings,
    tmp_path: Path,
    endpoint: str,
) -> None:
    config = query_settings.model_copy(update={"frontend_dist": tmp_path})
    conversation = create_conversation(config, ConversationCreate())
    fixed_end = datetime.fromisoformat("2026-10-11T12:00:00+08:00")
    start, end = fixed_end - timedelta(days=30), fixed_end
    questions = ["最近30天华东客户的订单数", "按天拆分", "改成最近7天", "按城市拆分", "用区域"]
    previous_id = None
    pending_id = None
    responses = []

    async def model(settings, question, schema, reference_time, **kwargs):
        nonlocal start, end
        context = kwargs["conversation_context"]
        position = questions.index(question)
        if position == 0:
            assert context.previous is None and context.clarification is None
        else:
            assert str(context.previous.run_id) == previous_id
            assert context.previous.draft.metrics == ["paid_orders"]
            assert context.previous.draft.filters == ["客户区域=华东", "订单已支付"]
        if position == 2:
            assert context.previous.draft.group_by == ["支付日期"]
            start, end = reference_time - timedelta(days=7), reference_time
        mode = "new" if position == 0 else "follow_up" if position < 4 else "clarification"
        grouping = ["支付日期"] if 1 <= position <= 3 else ["客户区域"] if position == 4 else []
        if position == 4:
            assert str(context.clarification.run_id) == pending_id
            assert context.clarification.draft.resolved_question.startswith("华东")
            assert context.clarification.draft.group_by == ["支付日期"]
        draft = QueryDraft(
            action="clarify" if position == 3 else "query",
            sql="" if position == 3 else "SELECT 1",
            context_mode=mode,
            resolved_question="华东已支付订单数，按"
            + ("客户区域" if position == 4 else "支付日期"),
            metrics=["paid_orders"],
            time_range=f"{start.isoformat()} 至 {end.isoformat()}",
            filters=["客户区域=华东", "订单已支付"],
            group_by=grouping,
            clarification="没有客户城市字段，是否使用客户区域？" if position == 3 else "",
        )
        if position != 3:
            dimension = "date_trunc('day', o.paid_at)" if grouping == ["支付日期"] else "c.region"
            draft.sql = (
                f"SELECT {dimension + ', ' if grouping else ''}COUNT(DISTINCT o.id) AS orders "
                "FROM whitebear_business.orders o "
                "JOIN whitebear_business.customers c ON c.id = o.customer_id "
                f"WHERE o.paid_at >= TIMESTAMPTZ '{start.isoformat()}' "
                f"AND o.paid_at < TIMESTAMPTZ '{end.isoformat()}' "
                "AND c.region = '华东' AND o.status = 'paid' "
                + ("GROUP BY 1 ORDER BY 1" if grouping else "")
            )
        return draft, {}

    for index, question in enumerate(questions):
        # Start a fresh app for every turn: all inheritance must come from the application DB.
        with (
            patch("app.agent.graph.generate_draft", side_effect=model),
            TestClient(create_app(config)) as client,
        ):
            response = client.post(
                f"/api/v1/conversations/{conversation.id}/{endpoint}",
                json={"question": question},
            )
            assert response.status_code == 200, response.text
            if endpoint.endswith("stream"):
                events = [
                    json.loads(line[6:])
                    for line in response.text.splitlines()
                    if line.startswith("data: ")
                ]
                run = events[-1]["run"]
                assert events[0]["run"]["input_context"] == run["input_context"]
            else:
                run = response.json()
            assert run["status"] == ("clarification_required" if index == 3 else "succeeded"), (
                run["error_code"],
                run["error_message"],
                run["steps"],
            )
            responses.append(run)
            if index == 3:
                pending_id = run["id"]
            else:
                previous_id = run["id"]
        if index == 0:
            # Newer failures and cancellations must not replace the successful inheritance source.
            for status in ("failed", "cancelled"):
                ignored = new_run(config, conversation.id, "无效的另一组条件")
                create_run(config, ignored)
                ignored.status = status
                ignored.completed_at = ignored.created_at
                ignored.draft = QueryDraft(
                    action="query", sql="SELECT 1", filters=["客户区域=华南"]
                )
                save_run(config, ignored)

    dataset = generate_dataset(GenerationOptions(as_of=fixed_end, orders=1500))
    east_customers = {row["id"] for row in dataset.rows["customers"] if row["region"] == "华东"}
    expected = sum(
        1
        for row in dataset.rows["orders"]
        if row["customer_id"] in east_customers
        and row["paid_at"] is not None
        and start <= row["paid_at"] < end
    )
    assert responses[-1]["result"]["rows"] == [["华东", expected]]
    assert responses[1]["draft"]["time_range"] == responses[0]["draft"]["time_range"]
    assert responses[2]["draft"]["time_range"] != responses[1]["draft"]["time_range"]
    with TestClient(create_app(config)) as client:
        assert client.get(f"/api/v1/runs/{responses[-1]['id']}").json() == responses[-1]

    # A completed clarification closes the pending request; a different conversation is empty.
    after = new_run(config, conversation.id, "新问题")
    create_run(config, after)
    assert after.input_context.previous.run_id == UUID(responses[-1]["id"])
    assert after.input_context.clarification is None
    other = create_conversation(config, ConversationCreate())
    independent = new_run(config, other.id, "按天拆分")
    create_run(config, independent)
    assert independent.input_context.previous is None
    assert independent.input_context.clarification is None
