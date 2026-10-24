"""Main FastAPI application entry point."""
import asyncio
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from app.api.audit import router as audit_router
from app.api.intents import router as intents_router
from app.api.mandates import router as mandates_router
from app.api.webhooks import router as webhooks_router
from app.core.database import AsyncSessionLocal, Base, engine
from app.services.budget import budget_service
from app.services.scheduler import escalation_expiry_loop, payout_polling_loop

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: DB init, Redis rebuild, background tasks."""
    # 1. Create tables
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialized successfully")
    except Exception as exc:
        logger.warning("Could not initialize database tables on startup: %s", exc)

    # 2. Rebuild budget counters from Postgres into Redis
    try:
        async with AsyncSessionLocal() as session:
            await budget_service.rebuild_from_db(session)
    except Exception as exc:
        logger.warning("Could not rebuild Redis budget from database on startup: %s", exc)

    # 3. Start background tasks
    expiry_task = asyncio.create_task(escalation_expiry_loop())
    polling_task = asyncio.create_task(payout_polling_loop())
    logger.info("Background scheduler tasks started")

    yield

    # 4. Clean shutdown: cancel and await background tasks
    expiry_task.cancel()
    polling_task.cancel()
    await asyncio.gather(expiry_task, polling_task, return_exceptions=True)
    logger.info("Background scheduler tasks stopped")


app = FastAPI(
    title="Agent Payment Firewall",
    description="Real-time guardrail proxy and risk evaluation system for autonomous AI payments.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(mandates_router)
app.include_router(webhooks_router)
app.include_router(intents_router)
app.include_router(audit_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint to verify backend service availability."""
    return {"status": "OK"}
