from fastapi import (
    APIRouter,
    BackgroundTasks,
    Header,
    HTTPException,
)
from fastapi.responses import JSONResponse

from app.config import settings
from app.models import JenkinsWebhookEvent
from app.services.incident_service import IncidentService


router = APIRouter()

incident_service = IncidentService()


async def _process_failure(
    job_name: str,
    build_number: int,
):

    try:

        await incident_service.process_failure(
            job_name=job_name,
            build_number=build_number,
        )

    except Exception as exc:

        print(
            "AutoHeal background processing failed "
            f"for {job_name} #{build_number}: {exc}"
        )


@router.post("/jenkins")
async def jenkins_webhook(
    event: JenkinsWebhookEvent,
    background_tasks: BackgroundTasks,
    x_autoheal_secret: str | None = Header(
        default=None
    ),
):

    if x_autoheal_secret != settings.webhook_secret:

        raise HTTPException(
            status_code=401,
            detail="Invalid webhook secret",
        )

    if event.status.upper() != "FAILURE":

        return {
            "message": (
                "Build is not a failure. "
                "No incident created."
            ),
            "job": event.job_name,
            "build": event.build_number,
            "status": event.status,
        }

    background_tasks.add_task(
        _process_failure,
        event.job_name,
        event.build_number,
    )

    return JSONResponse(
        status_code=202,
        content={
            "message": (
                "Failure accepted for "
                "asynchronous processing."
            ),
            "job": event.job_name,
            "build": event.build_number,
            "status": event.status,
        },
    )