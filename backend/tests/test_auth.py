"""Optional bearer-token auth + CORS origin policy."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import create_app

TOKEN = "test-token-123"


# ---------------------------------------------------------------------------
# token auth


@pytest.fixture()
def locked_api(monkeypatch) -> TestClient:
    monkeypatch.setenv("AFR_API_TOKEN", TOKEN)
    return TestClient(create_app())


def test_api_is_open_when_no_token(api):
    # zero-config localhost default: no token => no auth
    assert api.get("/runs").status_code == 200


def test_token_required_when_set(monkeypatch, api):
    monkeypatch.setenv("AFR_API_TOKEN", "s3cr3t-token")
    assert api.get("/runs").status_code == 401
    assert api.get("/runs", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert api.get("/runs", headers={"Authorization": "Bearer s3cr3t-token"}).status_code == 200
    # alternate header also accepted
    assert api.get("/runs", headers={"X-AFR-Token": "s3cr3t-token"}).status_code == 200


def test_health_stays_open_even_with_token(monkeypatch, api):
    monkeypatch.setenv("AFR_API_TOKEN", "s3cr3t-token")
    assert api.get("/health").status_code == 200


def test_all_api_router_mounts_are_guarded(locked_api):
    assert locked_api.get("/runs").status_code == 401
    assert locked_api.get("/api/runs").status_code == 401
    assert locked_api.get("/license").status_code == 401
    assert locked_api.post("/mcp/call", json={"tool": "x"}).status_code == 401
    assert locked_api.post("/demo/seed").status_code == 401


def test_wrong_or_malformed_token_rejected(locked_api):
    assert locked_api.get("/runs", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert locked_api.get("/runs", headers={"Authorization": TOKEN}).status_code == 401


def test_401_includes_www_authenticate_and_hint(locked_api):
    response = locked_api.get("/runs")
    assert response.headers.get("www-authenticate") == "Bearer"
    assert "AFR_API_TOKEN" in response.json()["detail"]["hint"]


def test_write_routes_are_guarded_too(monkeypatch, api):
    monkeypatch.setenv("AFR_API_TOKEN", "s3cr3t-token")
    # unauthenticated POST is rejected
    assert api.post("/runs", json={"name": "x"}).status_code == 401
    # authenticated POST works
    auth = {"Authorization": "Bearer s3cr3t-token"}
    assert api.post("/runs", json={"name": "x"}, headers=auth).status_code == 201


def test_sdk_client_attaches_token(monkeypatch):
    from afr.client import AFRClient

    monkeypatch.setenv("AFR_API_TOKEN", "tok-xyz")
    client = AFRClient(api_url="http://test.invalid")
    try:
        assert client._http.headers.get("authorization") == "Bearer tok-xyz"
    finally:
        client.close()


# ---------------------------------------------------------------------------
# CORS policy


def test_cors_default_is_not_wildcard(monkeypatch):
    monkeypatch.delenv("AFR_CORS_ORIGINS", raising=False)
    origins = config.cors_origins()
    assert "*" not in origins
    assert origins and all(o.startswith("http") for o in origins)


def test_cors_empty_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("AFR_CORS_ORIGINS", "")
    assert config.cors_origins() == config.DEFAULT_DEV_ORIGINS


def test_cors_wildcard_is_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("AFR_CORS_ORIGINS", "*")
    assert config.cors_origins() == ["*"]


def test_cors_custom_list(monkeypatch):
    monkeypatch.setenv("AFR_CORS_ORIGINS", "https://a.example, https://b.example")
    assert config.cors_origins() == ["https://a.example", "https://b.example"]
