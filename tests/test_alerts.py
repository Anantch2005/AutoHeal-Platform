
from fastapi.testclient import TestClient

from app.api import alerts as alerts_module
from app.main import app


class FakeResponse:
    def raise_for_status(self):
        return None


class FakeAsyncClient:
    calls = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse()


def test_alertmanager_sends_slack_notification_when_configured(monkeypatch):
    FakeAsyncClient.calls = []
    monkeypatch.setattr(alerts_module.settings, "slack_webhook_url", "https://hooks.slack.test/example")
    monkeypatch.setattr(alerts_module.httpx, "AsyncClient", FakeAsyncClient)

    response = TestClient(app).post(
        "/alerts/alertmanager",
        headers={"Authorization": "Bearer change-me-alertmanager"},
        json={
            "status": "firing",
            "alerts": [
                {
                    "labels": {"alertname": "AutoHealEscalated", "severity": "critical"},
                    "annotations": {"summary": "Incident requires human review"},
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["human_notification"] == "sent"
    assert len(FakeAsyncClient.calls) == 1
    url, payload = FakeAsyncClient.calls[0]
    assert url == "https://hooks.slack.test/example"
    assert "AutoHealEscalated" in payload["json"]["text"]

