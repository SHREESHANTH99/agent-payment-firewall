"""API package."""
from app.api.admin import router as admin_router
from app.api.audit import router as audit_router
from app.api.intents import router as intents_router
from app.api.mandates import router as mandates_router
from app.api.webhooks import router as webhooks_router

__all__ = ["admin_router", "audit_router", "intents_router", "mandates_router", "webhooks_router"]
