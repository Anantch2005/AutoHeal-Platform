from fastapi import FastAPI

from app.api.webhook import router as webhook_router


app = FastAPI(
    title="AutoHeal",
    description="Self-healing CI/CD platform",
    version="0.1.0",
)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "autoheal",
    }


app.include_router(
    webhook_router,
    prefix="/webhook",
)