from fastapi import APIRouter

from app.api.v1.endpoints.datasources import router as datasources_router
from app.api.v1.endpoints.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(datasources_router)
