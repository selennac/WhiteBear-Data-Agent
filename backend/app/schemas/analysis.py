"""Contracts for the first, single-question analysis workflow."""

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

    @model_validator(mode="after")
    def require_action_content(self) -> "QueryDraft":
        if self.action == "query" and not self.sql.strip():
            raise ValueError("查询方案必须包含 SQL。")
        if self.action == "clarify" and not self.clarification.strip():
            raise ValueError("澄清方案必须包含问题。")
        return self


class QueryColumn(BaseModel):
    name: str
    data_type: str


class QueryResult(BaseModel):
    columns: list[QueryColumn]
    rows: list[list[Cell]]
    row_count: int
    truncated: bool
    elapsed_ms: int


class RunStep(BaseModel):
    node: str
    status: Literal["succeeded", "failed"]
    attempt: int
    elapsed_ms: int
    detail: str = ""


class AnalysisRun(BaseModel):
    id: UUID
    conversation_id: UUID
    question: str
    status: Literal["running", "succeeded", "failed", "clarification_required"]
    created_at: datetime
    completed_at: datetime | None = None
    reference_time: datetime
    schema_version: str = ""
    prompt_version: str = "query-v1"
    model: str = ""
    draft: QueryDraft | None = None
    result: QueryResult | None = None
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
