"""Cancel blocking DB work and wait for its connection cleanup before returning."""

import asyncio
from collections.abc import Callable
from contextvars import ContextVar
from threading import Event, Lock
from typing import Any


class WorkCancelled(Exception):
    pass


class BlockingWork:
    def __init__(self) -> None:
        self.cancelled = Event()
        self.lock = Lock()
        self.connections: list[Any] = []

    def check(self) -> None:
        if self.cancelled.is_set():
            raise WorkCancelled()

    def register(self, connection: Any) -> None:
        with self.lock:
            self.connections.append(connection)
        self.check()

    def cancel_connections(self) -> None:
        with self.lock:
            connections = list(self.connections)
        for connection in connections:
            try:
                if not connection.closed:
                    connection.cancel_safe(timeout=1)
            except Exception:
                # Cleanup must not expose driver errors or prevent other connections closing.
                pass


current_work: ContextVar[BlockingWork | None] = ContextVar("blocking_work", default=None)


async def finish_task[T](task: asyncio.Task[T]) -> T:
    """Finish cleanup even if the owning request receives additional cancellation."""
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            if task.cancelled():
                raise
    return task.result()


async def run_blocking[T](action: Callable[..., T], *args: Any) -> T:
    work = BlockingWork()

    def call() -> T:
        token = current_work.set(work)
        try:
            work.check()
            return action(*args)
        finally:
            current_work.reset(token)

    task = asyncio.create_task(asyncio.to_thread(call))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        work.cancelled.set()
        await finish_task(asyncio.create_task(asyncio.to_thread(work.cancel_connections)))
        try:
            await finish_task(task)
        except Exception:
            pass
        raise
