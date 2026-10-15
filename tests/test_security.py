
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_webhook_requires_secret():
    response = client.post(
        "/webhook/jenkins",
        json={
            "job_name": "prac",
            "build_number": 999,
            "status": "FAILURE",
        },
    )

    assert response.status_code == 401


def test_alertmanager_requires_secret():
    response = client.post(
        "/alerts/alertmanager",
        json={
            "status": "firing",
            "alerts": [],
        },
    )

    assert response.status_code in (401, 403)

def test_alertmanager_accepts_matching_bearer_secret():
    response = client.post(
        "/alerts/alertmanager",
        headers={"Authorization": "Bearer change-me-alertmanager"},
        json={"status": "firing", "alerts": []},
    )
    assert response.status_code == 200
    assert response.json()["human_notification"] in {"sent", "not_configured", "failed"}

