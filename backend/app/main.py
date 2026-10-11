"""FastAPI application factory and ASGI entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.router import api_router
from app.core.config import Settings
from app.services.streaming import RunManager


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an app without connecting to databases or invoking a model."""
    config = settings if settings is not None else Settings()
    manager = RunManager()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await manager.shutdown()

    application = FastAPI(
        title=config.app_name,
        description="WhiteBearDataAgent 本地 TextToSQL 工作台 API。",
        version=__version__,
        lifespan=lifespan,
    )
    # Web requests only receive runtime credentials; provisioning remains CLI-only.
    application.state.settings = config.model_copy(
        update={"admin_database_url": None, "business_database_url": None}
    )
    application.state.runs = manager
    application.include_router(api_router, prefix="/api/v1")

    # Register the UI last so API and documentation routes take precedence.
    if (config.frontend_dist / "index.html").is_file():
        application.mount("/", StaticFiles(directory=config.frontend_dist, html=True), name="ui")

    return application


app = create_app()
