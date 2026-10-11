import asyncio
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.main import create_app
from app.repositories.analysis import RecordNotFoundError
from app.schemas.analysis import AnalysisRun
from app.services.analysis import analyze


def test_request_validation_and_unconfigured_model(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, frontend_dist=tmp_path, qwen_api_key=None)
    path = f"/api/v1/conversations/{uuid4()}/messages"
    with TestClient(create_app(settings)) as client:
        assert client.post(path, json={"question": "   "}).status_code == 422
        assert client.post(path, json={"question": "x" * 2001}).status_code == 422
        assert client.post(path, json={"question": "订单数", "sql": "DELETE"}).status_code == 422
        assert client.get("/api/v1/runs/invalid-uuid").status_code == 422
        response = client.post(path, json={"question": "订单数"})
        assert response.status_code == 503
        assert "QWEN_API_KEY" in response.json()["detail"]


def test_history_errors_are_safe(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, frontend_dist=tmp_path)
    error = OperationalError("SQL private", {}, Exception("password=private"))
    with TestClient(create_app(settings)) as client:
        with patch("app.api.v1.endpoints.analysis.list_conversations", side_effect=error):
            response = client.get("/api/v1/conversations")
            assert response.status_code == 503
            assert "private" not in response.text
        with patch(
            "app.api.v1.endpoints.analysis.get_run", side_effect=RecordNotFoundError("不存在")
        ):
            assert client.get(f"/api/v1/runs/{uuid4()}").status_code == 404


def test_unexpected_graph_failure_is_saved_without_credentials() -> None:
    settings = Settings(_env_file=None, qwen_api_key=SecretStr("private"))
    with (
        patch("app.services.analysis.create_run") as create,
        patch("app.services.analysis.run_graph", side_effect=RuntimeError("password=private")),
        patch("app.services.analysis.save_run") as save,
    ):
        result = asyncio.run(analyze(settings, uuid4(), "订单数"))
    create.assert_called_once()
    save.assert_called_once_with(settings, result)
    assert result.status == "failed"
    assert result.completed_at is not None
    assert "private" not in result.model_dump_json()


def test_run_response_contract(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    result = AnalysisRun(
        id=uuid4(),
        conversation_id=uuid4(),
        question="订单数",
        status="failed",
        created_at=now,
        reference_time=now,
        error_code="unsafe_sql",
    )
    settings = Settings(_env_file=None, frontend_dist=tmp_path)
    with patch("app.api.v1.endpoints.analysis.analyze", return_value=result):
        with TestClient(create_app(settings)) as client:
            response = client.post(
                f"/api/v1/conversations/{result.conversation_id}/messages",
                json={"question": "订单数"},
            )
    assert response.status_code == 200
    assert response.json()["id"] == str(result.id)
    assert response.json()["error_code"] == "unsafe_sql"


def test_json_and_stream_share_the_same_conversation_reservation(tmp_path: Path) -> None:
    app = create_app(Settings(_env_file=None, frontend_dist=tmp_path, qwen_api_key=None))
    conversation_id = uuid4()
    with TestClient(app) as client:
        app.state.runs.reserve(conversation_id)
        for endpoint in ("messages", "messages/stream"):
            response = client.post(
                f"/api/v1/conversations/{conversation_id}/{endpoint}", json={"question": "追问"}
            )
            assert response.status_code == 409
        app.state.runs.conversations.discard(conversation_id)
        for endpoint in ("messages", "messages/stream"):
            response = client.post(
                f"/api/v1/conversations/{conversation_id}/{endpoint}", json={"question": "追问"}
            )
            assert response.status_code == 503
            assert conversation_id not in app.state.runs.conversations
