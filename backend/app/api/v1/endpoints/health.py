from fastapi import APIRouter, Request

from app import __version__
from app.core.config import Settings
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    """Report process availability; this is not a database readiness check."""
    settings: Settings = request.app.state.settings
    return HealthResponse(app_name=settings.app_name, version=__version__)
