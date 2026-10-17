
import logging
import secrets
from typing import Any

import httpx
from fastapi import APIRouter, Header, HTTPException

from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/alertmanager")
async def alertmanager_webhook(
    payload: dict[str, Any],
    authorization: str | None = Header(default=None),
):
    """Authenticate Alertmanager and optionally deliver human-facing Slack alerts."""
    provided_secret = ""
    if authorization and authorization.lower().startswith("bearer "):
        provided_secret = authorization[7:].strip()
    if not secrets.compare_digest(provided_secret, settings.alertmanager_secret):
        raise HTTPException(status_code=401, detail="Invalid alertmanager secret")

    status = payload.get("status", "unknown")
    alerts = payload.get("alerts", [])
    alert_names = [
        str(alert.get("labels", {}).get("alertname", "unknown"))
        for alert in alerts
    ]
    logger.warning(
        "Alertmanager notification received: status=%s count=%d alerts=%s",
        status,
        len(alerts),
        ",".join(alert_names[:20]),
    )

    notification_status = "not_configured"
    if settings.slack_webhook_url:
        summaries = []
        for alert in alerts[:10]:
            labels = alert.get("labels", {})
            annotations = alert.get("annotations", {})
            summaries.append(
                f"• {labels.get('alertname', 'Unknown alert')} "
                f"[{labels.get('severity', 'unknown')}]: "
                f"{annotations.get('summary', 'No summary supplied')}"
            )
        message = (
            f"BuildSentry Alertmanager status: {status}\n"
            + ("\n".join(summaries) if summaries else "No alert details supplied.")
        )
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    settings.slack_webhook_url,
                    json={"text": message[:3500]},
                )
                response.raise_for_status()
            notification_status = "sent"
        except Exception:
            notification_status = "failed"
            logger.exception("Slack notification delivery failed")
    else:
        logger.warning(
            "SLACK_WEBHOOK_URL is not configured; alerts are logged but no "
            "external human notification will be delivered."
        )

    return {
        "status": "received",
        "alert_status": status,
        "alerts_received": len(alerts),
        "human_notification": notification_status,
    }