"""Optional bearer-token auth (AFR_API_TOKEN)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

TOKEN = "test-token-123"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture()
def locked_api(monkeypatch) -> TestClient:
    monkeypatch.setenv("AFR_API_TOKEN", TOKEN)
    return TestClient(create_app())


def test_no_token_env_keeps_instance_open(api):
    assert api.post("/runs", json={}).status_code == 201
    assert api.get("/runs").status_code == 200


def test_protected_routes_require_token(locked_api):
    assert locked_api.get("/runs").status_code == 401
    assert locked_api.post("/runs", json={}).status_code == 401
    assert locked_api.get("/api/runs").status_code == 401
    assert locked_api.post("/mcp/call", json={"tool": "x"}).status_code == 401


def test_wrong_or_malformed_token_rejected(locked_api):
    assert locked_api.get("/runs", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert locked_api.get("/runs", headers={"Authorization": TOKEN}).status_code == 401


def test_correct_token_grants_access(locked_api):
    created = locked_api.post("/runs", json={"name": "authed"}, headers=AUTH)
    assert created.status_code == 201
    run_id = created.json()["id"]
    assert locked_api.get(f"/runs/{run_id}", headers=AUTH).status_code == 200
    assert locked_api.get("/api/runs", headers=AUTH).status_code == 200


def test_health_and_license_stay_open(locked_api):
    assert locked_api.get("/health").status_code == 200
    assert locked_api.get("/license").status_code == 200


def test_401_includes_www_authenticate_and_hint(locked_api):
    response = locked_api.get("/runs")
    assert response.headers.get("www-authenticate") == "Bearer"
    assert "AFR_API_TOKEN" in response.json()["detail"]
