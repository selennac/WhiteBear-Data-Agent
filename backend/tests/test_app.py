from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health_and_openapi_without_external_services(tmp_path: Path) -> None:
    settings = Settings(app_name="Test Agent", frontend_dist=tmp_path, _env_file=None)
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "app_name": "Test Agent", "version": "0.1.0"}
        assert "/api/v1/health" in client.get("/openapi.json").json()["paths"]
        assert client.get("/api/v1/missing").status_code == 404


def test_built_frontend_does_not_shadow_api(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html>Workspace</html>", encoding="utf-8")
    settings = Settings(frontend_dist=tmp_path, _env_file=None)
    with TestClient(create_app(settings)) as client:
        assert client.get("/").text == "<html>Workspace</html>"
        assert client.get("/api/v1/health").json()["status"] == "ok"
        assert client.get("/api/v1/missing").status_code == 404
