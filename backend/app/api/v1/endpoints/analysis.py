"""Phase-two JSON endpoints; streaming and cancellation follow in phase three."""

from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.db.connections import DatabaseConfigurationError
from app.llm.query import ModelError
from app.repositories.analysis import (
    RecordNotFoundError,
    create_conversation,
    get_conversation,
    get_run,
    list_conversations,
)
from app.schemas.analysis import (
    AnalysisRun,
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
    MessageCreate,
)
from app.services.analysis import analyze

router = APIRouter(tags=["analysis"])


def operation[T](action: Callable[[], T]) -> T:
    try:
        return action()
    except RecordNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    except (DatabaseConfigurationError, ModelError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    except (SQLAlchemyError, ValidationError):
        raise HTTPException(
            status_code=503,
            detail="应用数据库暂不可用，请检查连接并运行 db init 更新迁移。",
        ) from None


@router.post("/conversations", response_model=ConversationSummary, status_code=201)
def create(body: ConversationCreate, request: Request) -> ConversationSummary:
    return operation(lambda: create_conversation(request.app.state.settings, body))


@router.get("/conversations", response_model=list[ConversationSummary])
def conversations(
    request: Request, offset: int = Query(default=0, ge=0)
) -> list[ConversationSummary]:
    return operation(lambda: list_conversations(request.app.state.settings, offset))


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def conversation(conversation_id: UUID, request: Request) -> ConversationDetail:
    return operation(lambda: get_conversation(request.app.state.settings, conversation_id))


@router.post("/conversations/{conversation_id}/messages", response_model=AnalysisRun)
def message(conversation_id: UUID, body: MessageCreate, request: Request) -> AnalysisRun:
    return operation(lambda: analyze(request.app.state.settings, conversation_id, body.question))


@router.get("/runs/{run_id}", response_model=AnalysisRun)
def run_detail(run_id: UUID, request: Request) -> AnalysisRun:
    return operation(lambda: get_run(request.app.state.settings, run_id))
