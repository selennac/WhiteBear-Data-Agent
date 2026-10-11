import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from app.agent.graph import EventSink, fail, run_graph
from app.core.async_work import finish_task, run_blocking
from app.core.config import Settings
from app.llm.query import PROMPT_VERSION, ModelError
from app.repositories.analysis import create_run, save_run
from app.schemas.analysis import AnalysisRun


def new_run(settings: Settings, conversation_id: UUID, question: str) -> AnalysisRun:
    if settings.qwen_api_key is None:
        raise ModelError("model_unconfigured", "请在 backend/.env 配置 QWEN_API_KEY。")
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    return AnalysisRun(
        id=uuid4(),
        conversation_id=conversation_id,
        question=question,
        status="running",
        created_at=now,
        reference_time=now,
        prompt_version=PROMPT_VERSION,
        model=settings.qwen_model,
    )


async def execute_run(
    settings: Settings, run: AnalysisRun, emit: EventSink = lambda event: None
) -> AnalysisRun:
    try:
        await asyncio.sleep(0)
        await run_graph(settings, run, emit)
    except asyncio.CancelledError:
        run.status = "cancelled"
        run.error_code = "run_cancelled"
        run.error_message = "分析已停止。"
        run.result = None
    except Exception:
        fail(run, "analysis_failed", "分析未能完成，请检查配置后重试。")
    run.completed_at = datetime.now(UTC)
    # A terminal event is only published after the final record has committed.
    await finish_task(asyncio.create_task(run_blocking(save_run, settings, run)))
    return run


async def analyze(settings: Settings, conversation_id: UUID, question: str) -> AnalysisRun:
    run = new_run(settings, conversation_id, question)
    await finish_task(asyncio.create_task(run_blocking(create_run, settings, run)))
    return await execute_run(settings, run)
