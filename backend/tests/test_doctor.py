"""afr doctor — setup diagnostics."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import afr
from afr_cli.main import run_doctor
from app.main import create_app


@pytest.fixture()
def sdk_client(api: TestClient) -> afr.AFRClient:
    return afr.AFRClient(http_client=api)


def test_doctor_healthy_backend(sdk_client, api, capsys):
    ok = run_doctor(sdk_client, "http://test", "default", read_only=False)
    out = capsys.readouterr().out
    assert ok
    assert "[ok]   backend reachable" in out
    assert "[ok]   license:" in out
    assert "[ok]   read access" in out
    assert "[ok]   write access" in out
    assert "all checks passed" in out
    # the write check leaves a completed run behind, visibly named
    runs = api.get("/runs").json()
    assert any(r["name"] == "afr-doctor-check" and r["status"] == "completed" for r in runs)


def test_doctor_read_only_skips_write(sdk_client, api, capsys):
    ok = run_doctor(sdk_client, "http://test", "default", read_only=True)
    out = capsys.readouterr().out
    assert ok
    assert "[skip] write check" in out
    assert api.get("/runs").json() == []


def test_doctor_reports_auth_failure(monkeypatch, capsys):
    # token-locked server; the injected TestClient sends no Authorization
    # header, so reads must 401 and doctor must say the token doesn't match
    monkeypatch.setenv("AFR_API_TOKEN", "server-side-secret")
    client = afr.AFRClient(http_client=TestClient(create_app()))

    ok = run_doctor(client, "http://test", "default", read_only=True)
    out = capsys.readouterr().out
    assert not ok
    assert "read access denied (401)" in out
    assert "AFR_API_TOKEN" in out


def test_doctor_unreachable_backend_prints_docker_hint(capsys):
    client = afr.AFRClient("http://127.0.0.1:9", timeout=0.5)
    try:
        ok = run_doctor(client, "http://127.0.0.1:9", "--api-url flag", read_only=True)
    finally:
        client.close()
    out = capsys.readouterr().out
    assert not ok
    assert "backend unreachable" in out
    assert "docker compose up --build" in out
    assert "http://127.0.0.1:8700" in out
