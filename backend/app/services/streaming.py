"""Per-app run ownership for the local, single-process workspace."""

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from uuid import UUID

from app.core.async_work import finish_task, run_blocking
from app.core.config import Settings
from app.repositories.analysis import create_run
from app.schemas.analysis import AnalysisEvent, AnalysisRun
from app.services.analysis import execute_run, new_run


class RunBusyError(ValueError):
    pass


@dataclass
class ActiveRun:
    run: AnalysisRun
    events: asyncio.Queue[AnalysisEvent | None] = field(default_factory=asyncio.Queue)
    task: asyncio.Task[None] | None = None
    stopping: bool = False
    started: asyncio.Event = field(default_factory=asyncio.Event)
    prepared: asyncio.Event = field(default_factory=asyncio.Event)

    def emit(self, event: AnalysisEvent) -> None:
        # The graph continues mutating drafts and steps after each publication.
        self.events.put_nowait(event.model_copy(deep=True))

    async def stream(self) -> AsyncIterator[str]:
        sequence = 0
        while True:
            try:
                event = await asyncio.wait_for(self.events.get(), timeout=10)
            except TimeoutError:
                yield ": heartbeat\n\n"
                continue
            if event is None:
                return
            sequence += 1
            payload = event.model_dump(mode="json", exclude_none=True)
            if event.run is not None:
                # Full run snapshots must match GET /runs, including optional null fields.
                payload["run"] = event.run.model_dump(mode="json")
            yield (
                f"id: {self.run.id}/{sequence}\nevent: {event.type}\n"
                f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            )


class RunManager:
    def __init__(self) -> None:
        self.active: dict[UUID, ActiveRun] = {}
        self.conversations: set[UUID] = set()
        self.closing = False

    def reserve(self, conversation_id: UUID) -> None:
        if self.closing:
            raise RunBusyError("服务正在停止，请稍后重试。")
        if conversation_id in self.conversations:
            raise RunBusyError("该会话已有运行中的分析，请先停止或等待完成。")
        self.conversations.add(conversation_id)

    async def start(self, settings: Settings, conversation_id: UUID, question: str) -> ActiveRun:
        self.reserve(conversation_id)
        try:
            active = ActiveRun(new_run(settings, conversation_id, question))
        except Exception:
            self.conversations.discard(conversation_id)
            raise
        self.active[active.run.id] = active
        write = asyncio.create_task(run_blocking(create_run, settings, active.run))
        try:
            await asyncio.shield(write)
        except asyncio.CancelledError:
            try:
                await finish_task(write)
                active.task = asyncio.create_task(self.execute(settings, active))
                active.prepared.set()
                await self.stop(active)
            finally:
                self.release(active)
                active.prepared.set()
            raise
        except Exception:
            self.release(active)
            active.prepared.set()
            raise
        active.emit(AnalysisEvent(type="run_started", run_id=active.run.id, run=active.run))
        active.task = asyncio.create_task(self.execute(settings, active))
        active.prepared.set()
        return active

    def release(self, active: ActiveRun) -> None:
        self.active.pop(active.run.id, None)
        self.conversations.discard(active.run.conversation_id)

    async def execute(self, settings: Settings, active: ActiveRun) -> None:
        active.started.set()
        try:
            await execute_run(settings, active.run, active.emit)
            active.emit(AnalysisEvent(type="run_completed", run_id=active.run.id, run=active.run))
        except Exception:
            active.emit(
                AnalysisEvent(
                    type="stream_error",
                    run_id=active.run.id,
                    error_message="运行状态未能保存，请检查应用数据库后刷新历史记录。",
                )
            )
        finally:
            self.release(active)
            active.events.put_nowait(None)

    async def stop(self, active: ActiveRun) -> None:
        await active.prepared.wait()
        if active.task is not None and not active.task.done():
            if not active.stopping:
                active.stopping = True
                await active.started.wait()
                if active.run.status == "running" and not active.task.done():
                    active.task.cancel()
            await finish_task(active.task)

    async def shutdown(self) -> None:
        self.closing = True
        tasks = [asyncio.create_task(self.stop(active)) for active in list(self.active.values())]
        if tasks:
            await asyncio.gather(*tasks)
