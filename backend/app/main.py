"""Main FastAPI application entry point."""
from fastapi import FastAPI

app = FastAPI(
    title="Agent Payment Firewall",
    description="Real-time guardrail proxy and risk evaluation system for autonomous AI payments.",
    version="0.1.0",
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint to verify backend service availability."""
    return {"status": "OK"}
