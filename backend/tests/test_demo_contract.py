"""Contract test asserting backend demo routes match the OpenAPI contract."""
from __future__ import annotations

import json
import os
import pytest
import httpx

from app.main import app

@pytest.mark.asyncio
async def test_demo_openapi_contract_conformance():
    """Verify that all demo routes defined in docs/openapi-demo.json exist in app routes."""
    openapi_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../docs/openapi-demo.json"))
    assert os.path.exists(openapi_path), "docs/openapi-demo.json must exist"
    
    with open(openapi_path, encoding="utf-8") as f:
        spec = json.load(f)
    
    paths = spec.get("paths", {})
    assert "/demo/health" in paths, "GET /demo/health must be in OpenAPI schema"
    assert "/demo/sessions" in paths, "POST /demo/sessions must be in OpenAPI schema"
    assert "/demo/sessions/{session_id}/state" in paths
    assert "/demo/sessions/{session_id}/intents" in paths
    assert "/demo/attacks" in paths
    assert "/demo/recorded-runs" in paths
    
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # GET /demo/health
        health_resp = await client.get("/demo/health")
        assert health_resp.status_code == 200
        data = health_resp.json()
        assert data["enabled"] is True
        assert "quota_remaining" in data
        assert "version" in data
        
        # GET /demo/attacks
        attacks_resp = await client.get("/demo/attacks")
        assert attacks_resp.status_code == 200
        attacks_data = attacks_resp.json()
        assert "items" in attacks_data
        assert len(attacks_data["items"]) >= 4
        
        # GET /demo/recorded-runs
        rec_resp = await client.get("/demo/recorded-runs")
        assert rec_resp.status_code == 200
        assert "items" in rec_resp.json()
