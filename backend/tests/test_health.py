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
