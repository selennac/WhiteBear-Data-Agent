"""Single-question graph with bounded repair and terminal safety failures."""

from time import perf_counter
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.core.config import Settings
from app.datasources.execution import QueryExecutionError, execute_query
from app.datasources.validation import SQLValidationError, validate_sql
from app.db.connections import DatabaseConfigurationError
from app.llm.query import ModelError, generate_draft
from app.schemas.analysis import AnalysisRun, QueryDraft, RunStep
from app.schemas.datasource import DatasourceSchema
from app.services.datasource import get_schema


class AnalysisState(TypedDict):
    run: AnalysisRun
    schema: DatasourceSchema | None
    draft: QueryDraft | None
    attempt: int
    diagnostic: str


def fail(run: AnalysisRun, code: str, message: str) -> None:
    run.status = "failed"
    run.error_code = code
    run.error_message = message


def step(
    state: AnalysisState,
    node: str,
    start: float,
    status: Literal["succeeded", "failed"] = "succeeded",
    detail: str = "",
) -> None:
    state["run"].steps.append(
        RunStep(
            node=node,
            status=status,
            attempt=state["attempt"],
            elapsed_ms=round((perf_counter() - start) * 1000),
            detail=detail,
        )
    )


def run_graph(settings: Settings, run: AnalysisRun) -> AnalysisRun:
    def load(state: AnalysisState) -> dict[str, object]:
        start = perf_counter()
        try:
            schema = get_schema(settings)
            run.schema_version = schema.schema_version
            step(state, "load_context", start)
            return {"schema": schema}
        except DatabaseConfigurationError as error:
            message = str(error)
        except Exception:
            message = "数据结构暂不可用，请检查数据库连接并运行 db init。"
        fail(run, "datasource_unavailable", message)
        step(state, "load_context", start, "failed", message)
        return {}

    def generate(state: AnalysisState) -> dict[str, object]:
        schema = state["schema"]
        assert schema is not None
        state["attempt"] += 1
        start = perf_counter()
        try:
            draft, usage = generate_draft(
                settings,
                run.question,
                schema,
                run.reference_time,
                previous_sql=state["draft"].sql if state["draft"] else "",
                diagnostic=state["diagnostic"],
            )
            for key, value in usage.items():
                run.token_usage[key] = run.token_usage.get(key, 0) + value
            known_metrics = {metric.id for metric in schema.metrics.metrics}
            if any(metric not in known_metrics for metric in draft.metrics):
                raise ModelError(
                    "model_output_invalid", "模型引用了未定义的指标，请依据业务口径修正。"
                )
            run.draft = draft
            step(state, "generate_query", start)
            if draft.action == "clarify":
                run.status = "clarification_required"
            return {"draft": draft, "attempt": state["attempt"], "diagnostic": ""}
        except ModelError as error:
            step(state, "generate_query", start, "failed", str(error))
            if error.code != "model_output_invalid" or state["attempt"] >= 3:
                fail(run, error.code, str(error))
            return {"attempt": state["attempt"], "diagnostic": str(error)}

    def validate(state: AnalysisState) -> dict[str, object]:
        schema, draft = state["schema"], state["draft"]
        assert schema is not None and draft is not None
        start = perf_counter()
        try:
            draft.sql = validate_sql(draft.sql, schema)
            step(state, "validate_sql", start)
            return {"draft": draft, "diagnostic": ""}
        except SQLValidationError as error:
            step(state, "validate_sql", start, "failed", str(error))
            if not error.retryable or state["attempt"] >= 3:
                fail(run, "invalid_sql" if error.retryable else "unsafe_sql", str(error))
            return {"diagnostic": str(error)}

    def execute(state: AnalysisState) -> dict[str, object]:
        schema, draft = state["schema"], state["draft"]
        assert schema is not None and draft is not None
        start = perf_counter()
        try:
            run.result = execute_query(settings, draft.sql, schema)
            run.status = "succeeded"
            step(state, "execute_query", start)
            return {"diagnostic": ""}
        except QueryExecutionError as error:
            step(state, "execute_query", start, "failed", str(error))
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
    graph.add_node("load", load)
    graph.add_node("generate", generate)
    graph.add_node("validate", validate)
    graph.add_node("execute", execute)
    graph.add_edge(START, "load")
    graph.add_conditional_edges("load", lambda state: END if run.status == "failed" else "generate")
    graph.add_conditional_edges("generate", after_generate)
    graph.add_conditional_edges("validate", after_validation)
    graph.add_conditional_edges(
        "execute", lambda state: END if run.status != "running" else "generate"
    )
    graph.compile().invoke(
        {
            "run": run,
            "schema": None,
            "draft": None,
            "attempt": 0,
            "diagnostic": "",
        }
    )
    return run
