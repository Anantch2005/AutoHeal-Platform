from fastapi import FastAPI

from opentelemetry.instrumentation.fastapi import (
    FastAPIInstrumentor,
)

from app.api.alerts import router as alerts_router
from app.api.webhook import router as webhook_router
from app.database.database import create_tables


create_tables()


app = FastAPI(
    title="AutoHeal",
    description="Self-healing CI/CD platform",
    version="0.6.0",
)


@app.get("/health")
async def health():
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