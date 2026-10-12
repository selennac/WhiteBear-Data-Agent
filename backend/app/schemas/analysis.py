"""Contracts for analysis records and incremental stream events."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Cell = str | int | float | bool | None


class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    datasource_id: Literal["business"] = "business"
    title: str = Field(default="新建分析", min_length=1, max_length=100)


class MessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=2000)
    context_run_id: UUID | None = None

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("请输入分析问题。")
        return value


class QueryDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["query", "clarify"]
    sql: str = Field(default="", max_length=20000)
    metrics: list[str] = Field(default_factory=list, max_length=20)
    time_range: str = Field(default="", max_length=1000)
    assumptions: list[str] = Field(default_factory=list, max_length=20)
    clarification: str = Field(default="", max_length=2000)
    context_mode: Literal["new", "follow_up", "clarification"] = "new"
    resolved_question: str = Field(default="", max_length=4000)
    filters: list[str] = Field(default_factory=list, max_length=20)
    group_by: list[str] = Field(default_factory=list, max_length=20)
    chart_intent: Literal["auto", "line", "bar", "pie", "table"] = "auto"

    @model_validator(mode="after")
    def require_action_content(self) -> "QueryDraft":
        if self.action == "query" and not self.sql.strip():
            raise ValueError("查询方案必须包含 SQL。")
        if self.action == "clarify" and not self.clarification.strip():
            raise ValueError("澄清方案必须包含问题。")
        return self


class ContextTurn(BaseModel):
    run_id: UUID
    question: str
    reference_time: datetime
    draft: QueryDraft


class ConversationContext(BaseModel):
    previous: ContextTurn | None = None
    clarification: ContextTurn | None = None


class QueryColumn(BaseModel):
    name: str
    data_type: str


class QueryResult(BaseModel):
    columns: list[QueryColumn]
    rows: list[list[Cell]]
    row_count: int
    truncated: bool
    elapsed_ms: int


class ChartSpec(BaseModel):
    """Column positions preserve duplicate SQL aliases; no executable chart options."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["line", "bar", "pie"]
    title: str = Field(max_length=200)
    x_column: int = Field(ge=0)
    y_columns: list[int] = Field(min_length=1, max_length=4)
    series_column: int | None = Field(default=None, ge=0)
    supported_types: list[Literal["line", "bar", "pie"]] = Field(min_length=1, max_length=3)


class SummaryNarrative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=4000)

    @field_validator("text")
    @classmethod
    def require_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("总结不能为空。")
        return value.strip()


class ResultSummary(SummaryNarrative):
    limitations: list[str] = Field(default_factory=list, max_length=10)


class RunStep(BaseModel):
    node: str
    status: Literal["running", "succeeded", "failed", "cancelled"]
    attempt: int
    elapsed_ms: int
    detail: str = ""


class AnalysisRun(BaseModel):
    id: UUID
    conversation_id: UUID
    question: str
    status: Literal["running", "succeeded", "failed", "clarification_required", "cancelled"]
    created_at: datetime
    completed_at: datetime | None = None
    reference_time: datetime
    schema_version: str = ""
    prompt_version: str = "query-v1"
    model: str = ""
    context_run_id: UUID | None = None
    input_context: ConversationContext = Field(default_factory=ConversationContext)
    draft: QueryDraft | None = None
    result: QueryResult | None = None
    chart: ChartSpec | None = None
    chart_message: str = ""
    summary: ResultSummary | None = None
    summary_error: str = ""
    summary_prompt_version: str = ""
    steps: list[RunStep] = Field(default_factory=list)
    token_usage: dict[str, int] = Field(default_factory=dict)
    error_code: str = ""
    error_message: str = ""


class ConversationSummary(BaseModel):
    id: UUID
    datasource_id: Literal["business"]
    title: str
    created_at: datetime


class ConversationDetail(ConversationSummary):
    runs: list[AnalysisRun]


class AnalysisEvent(BaseModel):
    type: Literal[
        "run_started",
        "node_status",
        "sql",
        "result",
        "chart",
        "summary",
        "run_completed",
        "stream_error",
    ]
    run_id: UUID
    run: AnalysisRun | None = None
    step: RunStep | None = None
    draft: QueryDraft | None = None
    result: QueryResult | None = None
    chart: ChartSpec | None = None
    chart_message: str = ""
    summary: ResultSummary | None = None
    summary_error: str = ""
    summary_prompt_version: str = ""
    schema_version: str = ""
    token_usage: dict[str, int] = Field(default_factory=dict)
    error_message: str = ""
