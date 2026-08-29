from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException

from app.config import settings


router = APIRouter()


@router.post("/alertmanager")
async def alertmanager_webhook(
    payload: dict[str, Any],
    x_autoheal_secret: str | None = Header(
        default=None,
    ),
):
    expected = getattr(
        settings,
        "alertmanager_secret",
        None,
    )

    if expected and x_autoheal_secret != expected:
        raise HTTPException(
            status_code=401,
            detail="Invalid alertmanager secret",
        )

    status = payload.get(
        "status",
        "unknown",
    )

    alerts = payload.get(
        "alerts",
        [],
    )

    print()
    print("=" * 60)
    print("AUTOHEAL ALERTMANAGER NOTIFICATION")
    print("=" * 60)

    print(
        f"Status      : {status}"
    )

    print(
        f"Alerts      : {len(alerts)}"
    )

    print(
        f"Received    : "
        f"{datetime.now(timezone.utc).isoformat()}"
    )

    for alert in alerts:

        labels = alert.get(
            "labels",
            {},
        )

        annotations = alert.get(
            "annotations",
            {},
        )

        print("-" * 60)

        print(
            f"Alert       : "
            f"{labels.get('alertname', 'unknown')}"
        )

        print(
            f"Severity    : "
            f"{labels.get('severity', 'unknown')}"
        )

        print(
            f"Service     : "
            f"{labels.get('service', 'unknown')}"
        )

        print(
            f"Summary     : "
            f"{annotations.get('summary', '')}"
        )

        print(
            f"Description : "
            f"{annotations.get('description', '')}"
        )

    print("=" * 60)

    return {
        "status": "received",
        "alert_status": status,
        "alerts_received": len(alerts),
    }