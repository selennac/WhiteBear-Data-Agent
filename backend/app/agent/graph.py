"""Conversation-aware query graph with incremental progress and bounded repair."""

import asyncio
from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import TypedDict

from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, START, StateGraph

from app.core.async_work import run_blocking
from app.core.config import Settings
from app.datasources.execution import QueryExecutionError, execute_query
from app.datasources.validation import SQLValidationError, validate_sql
from app.db.connections import DatabaseConfigurationError
from app.llm.query import ModelError, generate_draft
from app.schemas.analysis import AnalysisEvent, AnalysisRun, QueryDraft, RunStep
from app.schemas.datasource import DatasourceSchema
from app.services.datasource import get_schema


class AnalysisState(TypedDict):
    run: AnalysisRun
    schema: DatasourceSchema | None
    draft: QueryDraft | None
    attempt: int
    diagnostic: str


Node = Callable[[AnalysisState], Awaitable[dict[str, object]]]
EventSink = Callable[[AnalysisEvent], None]


def fail(run: AnalysisRun, code: str, message: str) -> None:
    run.status = "failed"
    run.error_code = code
    run.error_message = message


async def run_graph(
    settings: Settings, run: AnalysisRun, emit: EventSink = lambda event: None
) -> AnalysisRun:
    def publish_step(item: RunStep) -> None:
        emit(
            AnalysisEvent(
                type="node_status",
                run_id=run.id,
                step=item.model_copy(deep=True),
                schema_version=run.schema_version,
                token_usage=dict(run.token_usage),
            )
        )

    def publish_draft() -> None:
        emit(AnalysisEvent(type="sql", run_id=run.id, draft=run.draft))

    def tracked(name: str) -> Callable[[Node], Node]:
        def decorate(action: Node) -> Node:
            async def call(state: AnalysisState) -> dict[str, object]:
                if name == "generate_query":
                    state["attempt"] += 1
                start = perf_counter()
                item = RunStep(node=name, status="running", attempt=state["attempt"], elapsed_ms=0)
                run.steps.append(item)
                publish_step(item)
                try:
                    await asyncio.sleep(0)
                    update = await action(state)
                    diagnostic = str(update.get("diagnostic", ""))
                    item.status = "failed" if diagnostic or run.status == "failed" else "succeeded"
                    item.detail = diagnostic or run.error_message
                    return update
                except asyncio.CancelledError:
                    item.status = "cancelled"
                    item.detail = "分析已停止。"
                    raise
                except Exception:
                    item.status = "failed"
                    item.detail = "分析未能完成，请检查配置后重试。"
                    raise
                finally:
                    item.elapsed_ms = round((perf_counter() - start) * 1000)
                    publish_step(item)

            return call

        return decorate

    @tracked("load_context")
    async def load(state: AnalysisState) -> dict[str, object]:
        try:
            schema = await run_blocking(get_schema, settings)
            run.schema_version = schema.schema_version
            return {"schema": schema}
        except DatabaseConfigurationError as error:
            message = str(error)
        except Exception:
            message = "数据结构暂不可用，请检查数据库连接并运行 db init。"
        fail(run, "datasource_unavailable", message)
        return {}

    @tracked("generate_query")
    async def generate(state: AnalysisState) -> dict[str, object]:
        schema = state["schema"]
        assert schema is not None
        try:
            draft, usage = await generate_draft(
                settings,
                run.question,
                schema,
                run.reference_time,
                previous_sql=state["draft"].sql if state["draft"] else "",
                diagnostic=state["diagnostic"],
                conversation_context=run.input_context,
            )
            for key, value in usage.items():
                run.token_usage[key] = run.token_usage.get(key, 0) + value
            known_metrics = {metric.id for metric in schema.metrics.metrics}
            if any(metric not in known_metrics for metric in draft.metrics):
                raise ModelError(
                    "model_output_invalid", "模型引用了未定义的指标，请依据业务口径修正。"
                )
            source = {
                "new": True,
                "follow_up": run.input_context.previous is not None,
                "clarification": run.input_context.clarification is not None,
            }
            if not source[draft.context_mode]:
                raise ModelError("model_output_invalid", "该追问没有对应的历史，请澄清分析条件。")
            if not draft.resolved_question:
                draft.resolved_question = run.question
            run.draft = draft
            publish_draft()
            if draft.action == "clarify":
                run.status = "clarification_required"
            return {"draft": draft, "attempt": state["attempt"], "diagnostic": ""}
        except ModelError as error:
            if error.code != "model_output_invalid" or state["attempt"] >= 3:
                fail(run, error.code, str(error))
            return {"attempt": state["attempt"], "diagnostic": str(error)}

    @tracked("validate_sql")
    async def validate(state: AnalysisState) -> dict[str, object]:
        schema, draft = state["schema"], state["draft"]
        assert schema is not None and draft is not None
        try:
            draft.sql = validate_sql(draft.sql, schema)
            publish_draft()
            return {"draft": draft, "diagnostic": ""}
        except SQLValidationError as error:
            if not error.retryable or state["attempt"] >= 3:
                fail(run, "invalid_sql" if error.retryable else "unsafe_sql", str(error))
            return {"diagnostic": str(error)}

    @tracked("execute_query")
    async def execute(state: AnalysisState) -> dict[str, object]:
        schema, draft = state["schema"], state["draft"]
        assert schema is not None and draft is not None
        try:
            run.result = await run_blocking(execute_query, settings, draft.sql, schema)
            run.status = "succeeded"
            emit(AnalysisEvent(type="result", run_id=run.id, result=run.result))
            return {"diagnostic": ""}
        except QueryExecutionError as error:
            if not error.retryable or state["attempt"] >= 3:
                fail(run, error.code, str(error))
            return {"diagnostic": str(error)}

    def after_generate(state: AnalysisState) -> str:
        if run.status != "running":
            return END
        return "generate" if state["diagnostic"] else "validate"

    def after_validation(state: AnalysisState) -> str:
        if run.status != "running":
            return END
        return "generate" if state["diagnostic"] else "execute"

    graph = StateGraph(AnalysisState)
    graph.add_node("load", RunnableLambda(load))
    graph.add_node("generate", RunnableLambda(generate))
    graph.add_node("validate", RunnableLambda(validate))
    graph.add_node("execute", RunnableLambda(execute))
    graph.add_edge(START, "load")
    graph.add_conditional_edges("load", lambda state: END if run.status == "failed" else "generate")
    graph.add_conditional_edges("generate", after_generate)
    graph.add_conditional_edges("validate", after_validation)
    graph.add_conditional_edges(
        "execute", lambda state: END if run.status != "running" else "generate"
    )
    await graph.compile().ainvoke(
        {
            "run": run,
            "schema": None,
            "draft": None,
            "attempt": 0,
            "diagnostic": "",
        }
    )
    return run
