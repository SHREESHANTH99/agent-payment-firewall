"""Tests for the /health endpoint."""
import pytest
import httpx
from app.main import app


@pytest.mark.asyncio
async def test_health_check():
    """Verify that GET /health returns 200 OK."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "OK"}


@pytest.mark.asyncio
async def test_ready_check():
    """Verify that GET /ready returns 200 with healthy database and redis."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["checks"]["database"] == "healthy"
        assert data["checks"]["redis"] == "healthy"

