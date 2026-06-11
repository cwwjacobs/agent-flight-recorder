from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Every test gets its own SQLite file via AFR_DB_PATH."""
    monkeypatch.setenv("AFR_DB_PATH", str(tmp_path / "test-afr.db"))
    yield


@pytest.fixture()
def api() -> TestClient:
    return TestClient(create_app())
