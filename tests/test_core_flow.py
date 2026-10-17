
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.api import webhook as webhook_module
from app.collectors.jenkins import JenkinsBuild
from app.main import app
from app.services.incident_service import IncidentService


class FakeRepository:
    def __init__(self):
        self.events = []
        self.attempts = []
        self.final_status = None

    def exists(self, job_name, build_number):
        return False

    def create_incident(self, **kwargs):
        return 101

    def add_audit_event(self, **kwargs):
        self.events.append(kwargs)

    def count_attempts(self, incident_id):
        return len(self.attempts)

    def create_attempt(self, **kwargs):
        self.attempts.append(kwargs)

    def update_final_status(self, incident_id, final_status):
        self.final_status = final_status


def test_webhook_to_verified_recovery_with_mocked_jenkins(monkeypatch):
    """Exercise the real webhook/background-service flow with external I/O mocked."""
    service = IncidentService()
    repository = FakeRepository()
    service.repository = repository
    service.reporter.repository = repository
    service.ai_classifier.enabled = False
    service.jenkins.get_build_info = AsyncMock(
        return_value=JenkinsBuild(
            number=17,
            result="FAILURE",
            url="http://jenkins/job/prac/17/",
            console_log="/venv/bin/python: No module named pytest",
        )
    )
    service.remediation.execute = AsyncMock(
        return_value={
            "action": "CLEAN_DEPENDENCY_ENV_AND_RETRY",
            "success": True,
            "message": "Dependency environment reset; retry verified SUCCESS.",
            "new_build_number": 18,
            "verification_result": "SUCCESS",
            "queue_url": "http://jenkins/queue/item/123/",
        }
    )
    monkeypatch.setattr(webhook_module, "incident_service", service)

    response = TestClient(app).post(
        "/webhook/jenkins",
        headers={"X-BuildSentry-Secret": "change-me"},
        json={"job_name": "folder/prac", "build_number": 17, "status": "FAILURE"},
    )

    assert response.status_code == 202
    assert service.jenkins.get_build_info.await_count == 1
    service.remediation.execute.assert_awaited_once_with(
        job_name="folder/prac",
        category="DEPENDENCY_FAILURE",
        action="CLEAN_DEPENDENCY_ENV_AND_RETRY",
    )
    assert repository.final_status == "HEALED"
    assert any(event["event_type"] == "AUTOHEAL_RESULT" for event in repository.events)
    assert repository.attempts[0]["verification_result"] == "SUCCESS"


def test_code_failure_is_escalated_without_remediation(monkeypatch):
    service = IncidentService()
    repository = FakeRepository()
    service.repository = repository
    service.reporter.repository = repository
    service.ai_classifier.enabled = False
    service.jenkins.get_build_info = AsyncMock(
        return_value=JenkinsBuild(
            number=18,
            result="FAILURE",
            url="http://jenkins/job/prac/18/",
            console_log="AssertionError: expected 2 but got 1",
        )
    )
    service.remediation.execute = AsyncMock()
    monkeypatch.setattr(webhook_module, "incident_service", service)

    response = TestClient(app).post(
        "/webhook/jenkins",
        headers={"X-BuildSentry-Secret": "change-me"},
        json={"job_name": "folder/prac", "build_number": 18, "status": "FAILURE"},
    )

    assert response.status_code == 202
    service.remediation.execute.assert_not_awaited()
    assert repository.final_status == "ESCALATED"
    assert any(event["event_type"] == "POLICY_DENIED" for event in repository.events)