from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.api import webhook as webhook_module
from app.main import app
from app.models import (
    FailureClassification,
    Incident,
    RemediationResult,
)


client = TestClient(app)


def make_fake_incident():
    classification = FailureClassification(
        category="FLAKY_TEST",
        action="RETRY",
        reason="Known flaky test signature.",
        confidence=1.0,
        matched_pattern="AUTOHEAL_FLAKY_TEST",
    )

    return Incident(
        incident_id="AH-TEST1234",
        source="jenkins",
        job_name="prac",
        build_number=100,
        status="FAILURE",
        build_url="http://jenkins/job/prac/100/",
        console_log="AUTOHEAL_FLAKY_TEST",
        classification=classification,
        remediation=RemediationResult(
            action="RETRY",
            success=False,
            message="Test incident.",
        ),
    )


def test_webhook_failure_endpoint(monkeypatch):

    fake_service = AsyncMock()

    fake_service.process_failure.return_value = (
        make_fake_incident()
    )

    monkeypatch.setattr(
        webhook_module,
        "incident_service",
        fake_service,
    )

    response = client.post(
        "/webhook/jenkins",
        headers={
            "X-AutoHeal-Secret": "change-me",
        },
        json={
            "job_name": "prac",
            "build_number": 100,
            "build_url": (
                "http://jenkins/job/prac/100/"
            ),
            "status": "FAILURE",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["message"] == "Failure received"
    assert data["job"] == "prac"
    assert data["build"] == 100
    assert data["classification"]["category"] == (
        "FLAKY_TEST"
    )

    fake_service.process_failure.assert_awaited_once_with(
        job_name="prac",
        build_number=100,
    )


def test_webhook_rejects_invalid_secret():

    response = client.post(
        "/webhook/jenkins",
        headers={
            "X-AutoHeal-Secret": "wrong-secret",
        },
        json={
            "job_name": "prac",
            "build_number": 100,
            "status": "FAILURE",
        },
    )

    assert response.status_code == 401

    assert response.json()["detail"] == (
        "Invalid webhook secret"
    )


def test_webhook_ignores_non_failure_build():

    response = client.post(
        "/webhook/jenkins",
        headers={
            "X-AutoHeal-Secret": "change-me",
        },
        json={
            "job_name": "prac",
            "build_number": 100,
            "status": "SUCCESS",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "SUCCESS"

    assert data["message"] == (
        "Build is not a failure. No incident created."
    )