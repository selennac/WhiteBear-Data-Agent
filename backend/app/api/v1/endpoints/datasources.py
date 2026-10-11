from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.db.connections import DatabaseConfigurationError
from app.schemas.datasource import DatasourceSchema, DatasourceSummary, MetadataPatch
from app.services.datasource import InvalidMetadataError, get_schema, list_datasources

router = APIRouter(prefix="/datasources", tags=["datasources"])


def database_operation(
    source_id: str, operation: Callable[[], DatasourceSchema]
) -> DatasourceSchema:
    if source_id != "business":
        raise HTTPException(status_code=404, detail="数据源不存在。")
    try:
        return operation()
    except InvalidMetadataError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except DatabaseConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    except (SQLAlchemyError, ValidationError, OSError):
        # Database exceptions can include credentials or SQL parameters. Never return them.
        raise HTTPException(
            status_code=503, detail="数据源暂不可用，请检查数据库连接并运行 db init。"
        ) from None
    except ValueError:
        raise HTTPException(
            status_code=503, detail="业务库未正确初始化，请运行 db init。"
        ) from None


@router.get("", response_model=list[DatasourceSummary])
def datasources(request: Request) -> list[DatasourceSummary]:
    return list_datasources(request.app.state.settings)


@router.get("/{source_id}/schema", response_model=DatasourceSchema)
def schema(source_id: str, request: Request) -> DatasourceSchema:
    return database_operation(source_id, lambda: get_schema(request.app.state.settings))


@router.post("/{source_id}/sync", response_model=DatasourceSchema)
def sync(source_id: str, request: Request) -> DatasourceSchema:
    return database_operation(source_id, lambda: get_schema(request.app.state.settings, sync=True))


@router.patch("/{source_id}/metadata", response_model=DatasourceSchema)
def update_metadata(source_id: str, patch: MetadataPatch, request: Request) -> DatasourceSchema:
    return database_operation(
        source_id, lambda: get_schema(request.app.state.settings, patch=patch)
    )
