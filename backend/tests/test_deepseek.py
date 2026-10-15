import asyncio
import json
from datetime import datetime
from unittest.mock import patch

import httpx
import pytest
from pydantic import SecretStr
from test_query_model import context_schema

from app.core.config import Settings
from app.llm.query import ModelError, generate_draft
from app.llm.summary import generate_summary
from app.schemas.analysis import QueryColumn, QueryDraft, QueryResult


def test_deepseek_defaults_and_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DEEPSEEK_MODEL", "DEEPSEEK_BASE_URL", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=None)
    assert settings.deepseek_model == "deepseek-flash"
    assert settings.deepseek_base_url == "https://api.deepseek.com"
    assert settings.deepseek_api_key is None

    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-private-key")
    settings = Settings(_env_file=None)
    assert settings.deepseek_model == "deepseek-v4-pro"
    assert settings.deepseek_base_url == "https://api.deepseek.com/v1"
    assert settings.deepseek_api_key.get_secret_value() == "deepseek-private-key"
    assert "deepseek-private-key" not in settings.model_dump_json()


@pytest.mark.parametrize("kind", ["query", "summary"])
@pytest.mark.parametrize("empty", [False, True])
def test_deepseek_http_contract_and_empty_output(kind: str, empty: bool) -> None:
    settings = Settings(
        _env_file=None,
        deepseek_api_key=SecretStr("deepseek-private-key"),
        app_database_url=SecretStr("postgresql+psycopg://a:private-password@host/app"),
    )
    requests: list[httpx.Request] = []
    content = (
        {"action": "query", "sql": "SELECT 12 AS orders"}
        if kind == "query"
        else {"text": "当前条件下查询返回了 12 笔订单。"}
    )

    async def respond(
        client: httpx.AsyncClient, request: httpx.Request, **kwargs: object
    ) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            request=request,
            json={
                "id": "deepseek-stub",
                "object": "chat.completion",
                "model": settings.deepseek_model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "" if empty else json.dumps(content, ensure_ascii=False),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
            },
        )

    async def invoke():
        if kind == "query":
            return await generate_draft(
                settings, "订单数", context_schema(), datetime.now().astimezone()
            )
        return await generate_summary(
            settings,
            QueryDraft(action="query", sql="SELECT 12 AS orders"),
            QueryResult(
                columns=[QueryColumn(name="orders", data_type="integer")],
                rows=[[12]],
                row_count=1,
                truncated=False,
                elapsed_ms=1,
            ),
            context_schema(),
        )

    with patch("httpx.AsyncClient.send", new=respond):
        if empty:
            with pytest.raises(ModelError) as error:
                asyncio.run(invoke())
            assert error.value.code == (
                "model_output_invalid" if kind == "query" else "summary_output_invalid"
            )
            assert "private" not in str(error.value)
        else:
            parsed, usage = asyncio.run(invoke())
            if kind == "query":
                assert parsed.sql == content["sql"]
            else:
                assert parsed.text == content["text"]
            assert usage["input_tokens"] == 20
            assert usage["output_tokens"] == 10

    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == "https://api.deepseek.com/chat/completions"
    assert request.headers["authorization"] == "Bearer deepseek-private-key"
    payload = json.loads(request.content)
    assert payload["model"] == settings.deepseek_model
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["thinking"] == {"type": "disabled"}
    assert payload["max_tokens"] == (4096 if kind == "query" else 2048)
    assert "max_completion_tokens" not in payload
    assert "private" not in request.content.decode()
    timeout = (
        settings.llm_query_timeout_seconds
        if kind == "query"
        else settings.llm_summary_timeout_seconds
    )
    assert all(value == timeout for value in request.extensions["timeout"].values())
