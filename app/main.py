from fastapi import FastAPI, HTTPException

from opentelemetry.instrumentation.fastapi import (
    FastAPIInstrumentor,
)
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.alerts import router as alerts_router
from app.api.webhook import router as webhook_router
from app.database.database import create_tables, engine


create_tables()


app = FastAPI(
    title="AutoHeal",
    description="Self-healing CI/CD platform",
    version="0.7.0",
)


@app.get("/health")
async def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "service": "autoheal",
                "database": "disconnected",
                "observability": "enabled",
                "error": str(exc),
            },
        ) from exc

    return {
        "status": "healthy",
        "service": "autoheal",
        "database": "connected",
        "observability": "enabled",
    }


app.include_router(
    webhook_router,
    prefix="/webhook",
)

app.include_router(
    alerts_router,
    prefix="/alerts",
)


FastAPIInstrumentor.instrument_app(app)