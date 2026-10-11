"""JSON history, incremental analysis streams and explicit cancellation."""

import asyncio
from collections.abc import Callable
from typing import NoReturn
from uuid import UUID

import anyio
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.types import Receive, Scope, Send

from app.core.async_work import finish_task, run_blocking
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
    AnalysisEvent,
    AnalysisRun,
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
    MessageCreate,
)
from app.services.analysis import analyze
from app.services.streaming import ActiveRun, RunBusyError, RunManager

router = APIRouter(tags=["analysis"])


def http_error(error: Exception) -> NoReturn:
    if isinstance(error, RunBusyError):
        raise HTTPException(status_code=409, detail=str(error)) from None
    if isinstance(error, RecordNotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from None
    if isinstance(error, (DatabaseConfigurationError, ModelError)):
        raise HTTPException(status_code=503, detail=str(error)) from None
    if isinstance(error, (SQLAlchemyError, ValidationError)):
        raise HTTPException(
            status_code=503,
            detail="应用数据库暂不可用，请检查连接并运行 db init 更新迁移。",
        ) from None
    raise error


def operation[T](action: Callable[[], T]) -> T:
    try:
        return action()
    except Exception as error:
        http_error(error)


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
async def message(conversation_id: UUID, body: MessageCreate, request: Request) -> AnalysisRun:
    # Keep the original JSON contract available for scripts and API clients.
    manager: RunManager = request.app.state.runs
    try:
        manager.reserve(conversation_id)
        try:
            return await analyze(request.app.state.settings, conversation_id, body.question)
        finally:
            manager.conversations.discard(conversation_id)
    except Exception as error:
        http_error(error)


@router.get("/runs/{run_id}", response_model=AnalysisRun)
def run_detail(run_id: UUID, request: Request) -> AnalysisRun:
    return operation(lambda: get_run(request.app.state.settings, run_id))


class AnalysisStreamResponse(StreamingResponse):
    media_type = "text/event-stream"

    def __init__(self, manager: RunManager, active: ActiveRun) -> None:
        super().__init__(
            active.stream(),
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
        self.manager = manager
        self.active = active

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            # ASGI disconnect cancels the response task; cleanup owns an independent run task.
            with anyio.CancelScope(shield=True):
                await self.manager.stop(self.active)


@router.post(
    "/conversations/{conversation_id}/messages/stream",
    response_class=AnalysisStreamResponse,
    status_code=200,
    responses={
        200: {"model": AnalysisEvent, "description": "SSE 事件；run_completed 表示终态已保存。"}
    },
)
async def stream_message(
    conversation_id: UUID, body: MessageCreate, request: Request
) -> AnalysisStreamResponse:
    manager: RunManager = request.app.state.runs
    try:
        active = await manager.start(request.app.state.settings, conversation_id, body.question)
    except Exception as error:
        http_error(error)
    return AnalysisStreamResponse(manager, active)


@router.post("/runs/{run_id}/cancel", response_model=AnalysisRun)
async def cancel_run(run_id: UUID, request: Request) -> AnalysisRun:
    manager: RunManager = request.app.state.runs
    active = manager.active.get(run_id)
    if active is not None:
        await finish_task(asyncio.create_task(manager.stop(active)))
    record: AnalysisRun = await run_blocking(
        operation, lambda: get_run(request.app.state.settings, run_id)
    )
    if record.status == "running":
        raise HTTPException(
            status_code=409, detail="该运行不在当前服务中，请刷新历史并重新提交问题。"
        )
    return record
