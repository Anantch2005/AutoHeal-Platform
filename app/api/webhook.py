from fastapi import APIRouter, Header, HTTPException

from app.config import settings
from app.models import JenkinsWebhookEvent
from app.services.incident_service import IncidentService


router = APIRouter()

incident_service = IncidentService()


@router.post("/jenkins")
async def jenkins_webhook(
    event: JenkinsWebhookEvent,
    x_autoheal_secret: str | None = Header(default=None),
):

    if x_autoheal_secret != settings.webhook_secret:
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook secret",
        )

    if event.status.upper() != "FAILURE":
        return {
            "message": "Build is not a failure. No incident created.",
            "job": event.job_name,
            "build": event.build_number,
            "status": event.status,
        }

    incident = await incident_service.process_failure(
        job_name=event.job_name,
        build_number=event.build_number,
    )

    return {
        "message": "Failure received",
        "incident_id": incident.incident_id,
        "job": incident.job_name,
        "build": incident.build_number,
        "status": incident.status,
        "classification": incident.classification.model_dump(),
    }