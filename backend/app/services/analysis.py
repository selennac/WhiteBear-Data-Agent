from datetime import UTC, datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from app.agent.graph import fail, run_graph
from app.core.config import Settings
from app.llm.query import PROMPT_VERSION, ModelError
from app.repositories.analysis import create_run, save_run
from app.schemas.analysis import AnalysisRun


def analyze(settings: Settings, conversation_id: UUID, question: str) -> AnalysisRun:
    if settings.qwen_api_key is None:
        raise ModelError("model_unconfigured", "请在 backend/.env 配置 QWEN_API_KEY。")
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    run = AnalysisRun(
        id=uuid4(),
        conversation_id=conversation_id,
        question=question,
        status="running",
        created_at=now,
        reference_time=now,
        prompt_version=PROMPT_VERSION,
        model=settings.qwen_model,
    )
    create_run(settings, run)
    try:
        run_graph(settings, run)
    except Exception:
        fail(run, "analysis_failed", "分析未能完成，请检查配置后重试。")
    run.completed_at = datetime.now(UTC)
    save_run(settings, run)
    return run
