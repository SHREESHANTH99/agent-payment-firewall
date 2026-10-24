"""API package."""
from app.api.mandates import router as mandates_router
from app.api.webhooks import router as webhooks_router

__all__ = ["mandates_router", "webhooks_router"]
