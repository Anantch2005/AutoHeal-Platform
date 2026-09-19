from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.main import app


client = TestClient(app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_health_reports_database_failure():
    with patch(
        "app.main.engine.connect",
        side_effect=SQLAlchemyError("database unavailable"),
    ):
        response = client.get("/health")

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["status"] == "unhealthy"
    assert detail["database"] == "disconnected"