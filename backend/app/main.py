"""Main FastAPI application entry point."""
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI

from app.api.mandates import router as mandates_router
from app.api.webhooks import router as webhooks_router
from app.core.database import AsyncSessionLocal, Base, engine
from app.services.budget import budget_service

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown events."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialized successfully")
    except Exception as exc:
        logger.warning("Could not initialize database tables on startup: %s", exc)

    # Rebuild budget counters from Postgres into Redis
    try:
        async with AsyncSessionLocal() as session:
            await budget_service.rebuild_from_db(session)
    except Exception as exc:
        logger.warning("Could not rebuild Redis budget from database on startup: %s", exc)

    yield


app = FastAPI(
    title="Agent Payment Firewall",
    description="Real-time guardrail proxy and risk evaluation system for autonomous AI payments.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(mandates_router)
app.include_router(webhooks_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint to verify backend service availability."""
    return {"status": "OK"}
