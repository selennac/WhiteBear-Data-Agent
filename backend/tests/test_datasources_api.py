from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.main import create_app


def test_unconfigured_source_and_unknown_id_without_database(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        frontend_dist=tmp_path,
        app_database_url=None,
        business_readonly_database_url=None,
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/datasources").json()[0]["configured"] is False
        assert client.get("/api/v1/datasources/business/schema").status_code == 503
        assert client.get("/api/v1/datasources/unknown/schema").status_code == 404
        assert client.post("/api/v1/datasources/unknown/sync").status_code == 404


def test_database_error_does_not_return_credentials(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        frontend_dist=tmp_path,
        business_readonly_database_url=SecretStr("postgresql+psycopg://user:private@localhost/db"),
    )
    error = OperationalError("SQL private", {}, Exception("password=private"))
    with patch("app.services.datasource.discover_schema", side_effect=error):
        with TestClient(create_app(settings)) as client:
            response = client.get("/api/v1/datasources/business/schema")
            assert response.status_code == 503
            assert "private" not in response.text
