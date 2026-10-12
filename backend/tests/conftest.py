"""CI exercises the graph with a local model stub, never a real summary API call."""

from unittest.mock import AsyncMock

import pytest

from app.schemas.analysis import ResultSummary


@pytest.fixture(autouse=True)
def stub_result_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.agent.graph.generate_summary",
        AsyncMock(return_value=(ResultSummary(text="查询已完成，请结合表格与口径查看结果。"), {})),
    )
