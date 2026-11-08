"""Main FastAPI application entry point."""
import asyncio
import contextvars
from contextlib import asynccontextmanager
import logging
from typing import Any
import uuid

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.admin import router as admin_router
from app.api.agent import router as agent_router
from app.api.audit import router as audit_router
from app.api.intents import router as intents_router
from app.api.mandates import router as mandates_router
from app.api.webhooks import router as webhooks_router
from app.api.websocket import router as websocket_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal, Base, engine
from app.core.logging import setup_logging
from app.core.metrics import export_metrics
from app.core.security import metrics_auth
from app.services.budget import budget_service
from app.services.scheduler import escalation_expiry_loop, payout_polling_loop
from sqlalchemy import text

logger = logging.getLogger(__name__)

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")

INSECURE_OPERATOR_TOKENS = {
    "dev-operator-secret-token",
    "CHANGE_ME",
    "CHANGE_ME_IN_PRODUCTION",
    "operator-token",
    "default-operator-token",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: DB init, Redis rebuild, background tasks."""
    setup_logging()

    # Startup validation (enforced unless ENV == 'test')
    if settings.ENV.lower() != "test":
        if settings.PAYPAL_MODE.lower() != "sandbox":
            raise RuntimeError(
                f"FATAL: PAYPAL_MODE is '{settings.PAYPAL_MODE}'. Only 'sandbox' is permitted."
            )

        if (
            not settings.OPERATOR_TOKEN
            or len(settings.OPERATOR_TOKEN) < 24
            or settings.OPERATOR_TOKEN in INSECURE_OPERATOR_TOKENS
        ):
            raise RuntimeError(
                "FATAL: OPERATOR_TOKEN must be non-empty, at least 24 characters long, and not a known default."
            )

        if not settings.AGENT_API_KEYS:
            raise RuntimeError("FATAL: AGENT_API_KEYS must not be empty.")

        if not settings.DATABASE_URL:
            raise RuntimeError("FATAL: DATABASE_URL is missing.")

        if not settings.REDIS_URL:
            raise RuntimeError("FATAL: REDIS_URL is missing.")

    logger.info(
        "Application startup: PAYPAL_MODE=%s, EXECUTION_MODE=%s, ENV=%s",
        settings.PAYPAL_MODE,
        settings.EXECUTION_MODE,
        settings.ENV,
    )
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


# Docs availability: Disable /docs and /redoc in production unless ENABLE_DOCS=true
docs_url = "/docs"
redoc_url = "/redoc"
openapi_url = "/openapi.json"
if settings.ENV.lower() == "production" and not settings.ENABLE_DOCS:
    docs_url = None
    redoc_url = None
    openapi_url = None

app = FastAPI(
    title="Agent Payment Firewall",
    description="Real-time guardrail proxy and risk evaluation system for autonomous AI payments.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url,
)


class SecurityAndRequestIdMiddleware(BaseHTTPMiddleware):
    """Enforces request_id tracking, security headers, and request body size limit."""

    async def dispatch(self, request: Request, call_next):
        # 1. Request ID context and generation
        req_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:16]}"
        token = request_id_ctx.set(req_id)

        # 2. Body size check (default 256 KB)
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.MAX_REQUEST_BODY_BYTES:
            request_id_ctx.reset(token)
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={
                    "error": {
                        "code": "REQUEST_ENTITY_TOO_LARGE",
                        "message": f"Request body exceeds maximum allowed size ({settings.MAX_REQUEST_BODY_BYTES} bytes).",
                        "request_id": req_id,
                    }
                },
                headers={"X-Request-ID": req_id},
            )

        try:
            response = await call_next(request)
        except Exception:
            request_id_ctx.reset(token)
            raise

        request_id_ctx.reset(token)

        # 3. Security headers
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        if settings.ENABLE_DOCS and request.url.path in ["/docs", "/redoc", "/openapi.json"]:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https://fastapi.tiangolo.com;"
            )
        else:
            response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app.add_middleware(SecurityAndRequestIdMiddleware)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    req_id = request_id_ctx.get() or request.headers.get("X-Request-ID", "")
    code = "HTTP_ERROR"
    if exc.status_code == 404:
        code = "NOT_FOUND"
    elif exc.status_code == 401:
        code = "UNAUTHORIZED"
    elif exc.status_code == 403:
        code = "FORBIDDEN"
    elif exc.status_code == 429:
        code = "RATE_LIMIT_EXCEEDED"
    elif exc.status_code == 413:
        code = "REQUEST_ENTITY_TOO_LARGE"
    elif exc.status_code == 400:
        code = "BAD_REQUEST"

    headers = dict(getattr(exc, "headers", None) or {})
    headers["X-Request-ID"] = req_id
    # Consistent error response with backward-compatible top-level detail
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error": {
                "code": code,
                "message": exc.detail,
                "request_id": req_id,
            },
        },
        headers=headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    req_id = request_id_ctx.get() or request.headers.get("X-Request-ID", "")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": str(exc),
                "request_id": req_id,
            }
        },
        headers={"X-Request-ID": req_id},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    req_id = request_id_ctx.get() or request.headers.get("X-Request-ID", "")
    logger.exception("Unhandled server error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred.",
                "request_id": req_id,
            }
        },
        headers={"X-Request-ID": req_id},
    )

# CORS configuration restricted to DASHBOARD_ORIGIN
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.DASHBOARD_ORIGIN.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)

app.include_router(mandates_router)
app.include_router(agent_router)
app.include_router(webhooks_router)
app.include_router(intents_router)
app.include_router(audit_router)
app.include_router(admin_router)
app.include_router(websocket_router)
__import__("app.api.demo", fromlist=["register_demo"]).register_demo(app)


@app.get("/metrics")
async def prometheus_metrics(_: bool = Depends(metrics_auth)) -> Response:
    """Expose Prometheus metrics text format (authenticated)."""
    data, content_type = export_metrics()
    return Response(content=data, media_type=content_type)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint to verify backend service liveness."""
    return {"status": "OK"}


@app.get("/ready")
async def readiness_check() -> dict[str, Any]:
    """Readiness probe checking database and redis connectivity."""
    checks: dict[str, Any] = {"database": "unknown", "redis": "unknown"}
    all_ready = True

    # 1. Database check
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as exc:
        logger.error("Readiness check database error: %s", exc)
        checks["database"] = f"unhealthy: {type(exc).__name__}"
        all_ready = False

    # 2. Redis check
    try:
        r = await budget_service.get_redis()
        pong = await r.ping()
        checks["redis"] = "healthy" if pong else "unhealthy"
        if not pong:
            all_ready = False
    except Exception as exc:
        logger.error("Readiness check redis error: %s", exc)
        checks["redis"] = f"unhealthy: {type(exc).__name__}"
        all_ready = False


    status_code = 200 if all_ready else 503
    from fastapi.responses import JSONResponse, Response
    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if all_ready else "not_ready", "checks": checks},
    )

