from fastapi import FastAPI

from app.api.webhook import router as webhook_router
from app.database.database import create_tables


create_tables()


app = FastAPI(
    title="AutoHeal",
    description="Self-healing CI/CD platform",
    version="0.3.0",
)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "autoheal",
        "database": "connected",
    }


app.include_router(
    webhook_router,
    prefix="/webhook",
)