from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Every test gets its own SQLite file and a clean feature-flag slate."""
    monkeypatch.setenv("AFR_DB_PATH", str(tmp_path / "test-afr.db"))
    for var in ("AFR_PREMIUM_ENABLED", "AFR_REDACTION_ENABLED", "AFR_REDACT_KEYS"):
        monkeypatch.delenv(var, raising=False)
    yield


@pytest.fixture()
def api() -> TestClient:
    return TestClient(create_app())
