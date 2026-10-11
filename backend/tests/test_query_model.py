import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from openai import APITimeoutError, AuthenticationError, RateLimitError
from pydantic import SecretStr

from app.core.config import Settings
from app.llm.query import ModelError, generate_draft
from app.schemas.analysis import QueryDraft
from app.schemas.datasource import DatasourceSchema, MetricsDocument


def context_schema() -> DatasourceSchema:
    return DatasourceSchema(
        datasource_id="business",
        schema_name="whitebear_business",
        schema_version="fixed",
        tables=[],
        metrics=MetricsDocument(version="1", default_time_range_days=30, metrics=[]),
    )


@pytest.mark.parametrize("kind", ["timeout", "authentication", "rate_limit"])
def test_provider_failures_are_specific_and_do_not_expose_credentials(kind: str) -> None:
    request = httpx.Request("POST", "https://example.invalid")
    errors = {
        "timeout": APITimeoutError(request=request),
        "authentication": AuthenticationError(
            "private",
            response=httpx.Response(401, request=request),
            body={"secret": "private"},
        ),
        "rate_limit": RateLimitError(
            "private",
            response=httpx.Response(429, request=request),
            body={"secret": "private"},
        ),
    }
    settings = Settings(_env_file=None, qwen_api_key=SecretStr("private"))
    with patch("app.llm.query.ChatOpenAI") as model:
        model.return_value.with_structured_output.return_value.ainvoke = AsyncMock(
            side_effect=errors[kind]
        )
        with pytest.raises(ModelError) as error:
            asyncio.run(
                generate_draft(settings, "订单数", context_schema(), datetime.now().astimezone())
            )
    assert (
        error.value.code
        == {
            "timeout": "model_timeout",
            "authentication": "model_authentication_failed",
            "rate_limit": "model_rate_limited",
        }[kind]
    )
    assert "private" not in str(error.value)


def test_only_question_and_schema_context_are_sent_and_token_usage_is_kept() -> None:
    settings = Settings(
        _env_file=None,
        qwen_api_key=SecretStr("private-key"),
        app_database_url=SecretStr("postgresql+psycopg://account:private-password@host/app"),
    )
    now = datetime.fromisoformat("2026-10-11T12:00:00+08:00")
    draft = QueryDraft(action="query", sql="SELECT 1")
    with patch("app.llm.query.ChatOpenAI") as model:
        invoke = AsyncMock()
        model.return_value.with_structured_output.return_value.ainvoke = invoke
        invoke.return_value = {
            "parsed": draft,
            "raw": SimpleNamespace(usage_metadata={"input_tokens": 12}),
        }
        actual, usage = asyncio.run(generate_draft(settings, "订单数", context_schema(), now))
    context = invoke.call_args.args[0][1].content
    assert now.isoformat() in context
    assert "private-key" not in context and "private-password" not in context
    assert '"dataset"' not in context
    assert actual == draft and usage == {"input_tokens": 12}
