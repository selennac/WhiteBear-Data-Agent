import asyncio
import json
from pathlib import Path
from threading import Event
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.exc import OperationalError
from test_analysis_graph import result, schema

from app.api.v1.endpoints.analysis import AnalysisStreamResponse
from app.core.async_work import current_work, run_blocking
from app.core.config import Settings
from app.main import create_app
from app.schemas.analysis import AnalysisRun, QueryDraft
from app.services.streaming import RunBusyError, RunManager


def config() -> Settings:
    return Settings(_env_file=None, deepseek_api_key=SecretStr("stub"))


def parse_events(source: str) -> list[dict]:
    return [json.loads(line[6:]) for line in source.splitlines() if line.startswith("data: ")]


def test_stream_orders_progress_and_only_completes_after_save(tmp_path: Path) -> None:
    order: list[str] = []
    with (
        patch("app.services.streaming.create_run"),
        patch("app.services.analysis.save_run", side_effect=lambda *_: order.append("saved")),
        patch("app.agent.graph.get_schema", return_value=schema()),
        patch(
            "app.agent.graph.generate_draft",
            return_value=(QueryDraft(action="query", sql="SELECT 12"), {}),
        ),
        patch("app.agent.graph.execute_query", return_value=result()),
        TestClient(create_app(config().model_copy(update={"frontend_dist": tmp_path}))) as client,
    ):
        response = client.post(
            f"/api/v1/conversations/{uuid4()}/messages/stream",
            json={"question": "订单数"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["x-accel-buffering"] == "no"
        events = parse_events(response.text)
        assert order == ["saved"]
        assert events[0]["type"] == "run_started"
        assert events[-1]["type"] == "run_completed"
        assert events[-1]["run"]["status"] == "succeeded"
        statuses = [
            (e["step"]["node"], e["step"]["status"]) for e in events if e["type"] == "node_status"
        ]
        assert statuses == [
            (node, status)
            for node in [
                "load_context",
                "generate_query",
                "validate_sql",
                "execute_query",
                "build_chart",
                "summarize_result",
            ]
            for status in ["running", "succeeded"]
        ]
        assert any(e["type"] == "sql" for e in events)
        assert any(e["type"] == "result" for e in events)
        assert len(events[-1]["run"]["steps"]) == 6
        assert [e["type"] for e in events if e["type"] in {"result", "chart", "summary"}] == [
            "result",
            "chart",
            "summary",
        ]
        assert events[-1]["run"]["summary"]["text"]


def test_stream_preflight_errors_remain_http_errors(tmp_path: Path) -> None:
    with TestClient(
        create_app(Settings(_env_file=None, frontend_dist=tmp_path, deepseek_api_key=None))
    ) as client:
        response = client.post(
            f"/api/v1/conversations/{uuid4()}/messages/stream", json={"question": "订单数"}
        )
        assert response.status_code == 503
    error = OperationalError("private", {}, Exception("password=private"))
    with (
        patch("app.services.streaming.create_run", side_effect=error),
        TestClient(create_app(config().model_copy(update={"frontend_dist": tmp_path}))) as client,
    ):
        response = client.post(
            f"/api/v1/conversations/{uuid4()}/messages/stream", json={"question": "订单数"}
        )
        assert response.status_code == 503
        assert "private" not in response.text
        assert not client.app.state.runs.active


def test_cancel_during_model_call_saves_once_and_next_run_works() -> None:
    async def scenario() -> None:
        manager = RunManager()
        entered = asyncio.Event()
        closed = asyncio.Event()
        saved: list[AnalysisRun] = []

        async def slow_model(*args, **kwargs):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                closed.set()

        with (
            patch("app.services.streaming.create_run"),
            patch(
                "app.services.analysis.save_run",
                side_effect=lambda _, run: saved.append(run.model_copy(deep=True)),
            ),
            patch("app.agent.graph.get_schema", return_value=schema()),
            patch("app.agent.graph.generate_draft", side_effect=slow_model) as model,
            patch("app.agent.graph.execute_query", return_value=result()) as execute,
        ):
            conversation = uuid4()
            active = await manager.start(config(), conversation, "订单数")
            await asyncio.wait_for(entered.wait(), 2)
            with pytest.raises(RunBusyError):
                await manager.start(config(), conversation, "重复提交")
            await asyncio.wait_for(asyncio.gather(manager.stop(active), manager.stop(active)), 2)
            assert closed.is_set()
            assert active.run.status == "cancelled"
            assert active.run.steps[-1].status == "cancelled"
            assert active.run.completed_at is not None
            assert len(saved) == 1
            assert not manager.active
            execute.assert_not_called()
            model.side_effect = None
            model.return_value = (QueryDraft(action="query", sql="SELECT 12"), {})
            next_run = await manager.start(config(), conversation, "再问一次")
            await next_run.task
            assert next_run.run.status == "succeeded"
            assert len(saved) == 2

    asyncio.run(scenario())


def test_disconnect_cancels_owned_task_and_waits_for_cleanup() -> None:
    async def scenario() -> None:
        manager = RunManager()
        entered = asyncio.Event()
        closed = asyncio.Event()
        saved: list[AnalysisRun] = []

        async def slow_model(*args, **kwargs):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                closed.set()

        async def receive():
            await entered.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            pass

        with (
            patch("app.services.streaming.create_run"),
            patch(
                "app.services.analysis.save_run",
                side_effect=lambda _, run: saved.append(run.model_copy(deep=True)),
            ),
            patch("app.agent.graph.get_schema", return_value=schema()),
            patch("app.agent.graph.generate_draft", side_effect=slow_model),
        ):
            active = await manager.start(config(), uuid4(), "订单数")
            response = AnalysisStreamResponse(manager, active)
            await asyncio.wait_for(
                response({"type": "http", "asgi": {"spec_version": "2.0"}}, receive, send), 2
            )
            assert closed.is_set()
            assert saved[0].status == "cancelled"
            assert not manager.active

    asyncio.run(scenario())


def test_immediate_stop_and_shutdown_leave_terminal_records() -> None:
    async def scenario() -> None:
        manager = RunManager()
        with (
            patch("app.services.streaming.create_run"),
            patch("app.services.analysis.save_run") as save,
            patch("app.agent.graph.get_schema", return_value=schema()),
            patch(
                "app.agent.graph.generate_draft",
                return_value=(QueryDraft(action="query", sql="SELECT 12"), {}),
            ),
        ):
            first = await manager.start(config(), uuid4(), "订单数")
            await asyncio.wait_for(manager.stop(first), 2)
            assert first.run.status == "cancelled"
            second = await manager.start(config(), uuid4(), "销售额")
            await asyncio.wait_for(manager.shutdown(), 2)
            assert second.run.status == "cancelled"
            assert save.call_count == 2
            assert not manager.active

    asyncio.run(scenario())


def test_blocking_cancellation_waits_until_connection_is_closed() -> None:
    async def scenario() -> None:
        entered = Event()
        released = Event()

        class Connection:
            closed = False
            cancelled = False

            def cancel_safe(self, *, timeout):
                self.cancelled = True
                released.set()

        connection = Connection()

        def query():
            work = current_work.get()
            assert work is not None
            work.register(connection)
            entered.set()
            try:
                assert released.wait(2)
                work.check()
            finally:
                connection.closed = True

        task = asyncio.create_task(run_blocking(query))
        assert await asyncio.to_thread(entered.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
        assert connection.cancelled and connection.closed

    asyncio.run(scenario())


def test_persistence_failure_has_no_success_event() -> None:
    async def scenario() -> None:
        manager = RunManager()
        with (
            patch("app.services.streaming.create_run"),
            patch("app.services.analysis.save_run", side_effect=RuntimeError("password=private")),
            patch("app.agent.graph.get_schema", return_value=schema()),
            patch(
                "app.agent.graph.generate_draft",
                return_value=(QueryDraft(action="query", sql="SELECT 12"), {}),
            ),
            patch("app.agent.graph.execute_query", return_value=result()),
        ):
            active = await manager.start(config(), uuid4(), "订单数")
            source = "".join([frame async for frame in active.stream()])
            assert "private" not in source
            events = parse_events(source)
            assert events[-1]["type"] == "stream_error"
            assert not any(e["type"] == "run_completed" for e in events)
            assert not manager.active

    asyncio.run(scenario())


def test_shutdown_during_run_creation_waits_for_a_terminal_record() -> None:
    async def scenario() -> None:
        manager = RunManager()
        entered = Event()
        released = Event()

        def create(*args):
            entered.set()
            assert released.wait(2)

        with (
            patch("app.services.streaming.create_run", side_effect=create),
            patch("app.services.analysis.save_run") as save,
            patch("app.agent.graph.get_schema", return_value=schema()),
        ):
            start = asyncio.create_task(manager.start(config(), uuid4(), "订单数"))
            assert await asyncio.to_thread(entered.wait, 2)
            shutdown = asyncio.create_task(manager.shutdown())
            await asyncio.sleep(0)
            released.set()
            active = await asyncio.wait_for(start, 2)
            await asyncio.wait_for(shutdown, 2)
            assert active.run.status == "cancelled"
            assert save.call_count == 1
            assert not manager.active

    asyncio.run(scenario())
