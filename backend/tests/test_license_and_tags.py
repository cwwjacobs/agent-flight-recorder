"""License boundary placeholder + tags/notes endpoints."""

from __future__ import annotations

import pytest


@pytest.fixture()
def premium(monkeypatch):
    monkeypatch.setenv("AFR_PREMIUM_ENABLED", "true")


def test_license_endpoint_free(api):
    info = api.get("/license").json()
    assert info["premium"] is False
    assert info["plan"] == "free"
    assert info["features"]["recorder"] is True
    assert info["features"]["forked_replay"] is False
    assert "AFR_PREMIUM_ENABLED" in info["hint"]


def test_license_endpoint_premium(premium, api):
    info = api.get("/license").json()
    assert info["premium"] is True
    assert info["features"]["state_diff"] is True
    assert info["hint"] is None


def test_tags_notes_gated_in_free_mode(api):
    run_id = api.post("/runs", json={}).json()["id"]
    r = api.patch(f"/runs/{run_id}", json={"tags": ["x"]})
    assert r.status_code == 402
    assert r.json()["detail"]["feature"] == "tags_notes"


def test_tags_notes_and_tag_filter(premium, api):
    run_id = api.post("/runs", json={"name": "taggable"}).json()["id"]
    other_id = api.post("/runs", json={"name": "other"}).json()["id"]

    updated = api.patch(
        f"/runs/{run_id}",
        json={"tags": ["regression", "prod", "regression"], "notes": "Saw the bug here."},
    ).json()
    assert updated["tags"] == ["prod", "regression"]  # deduped + sorted
    assert updated["notes"] == "Saw the bug here."

    tagged = api.get("/runs", params={"tag": "regression"}).json()
    assert [r["id"] for r in tagged] == [run_id]
    assert other_id not in [r["id"] for r in tagged]

    # rename via the same endpoint
    renamed = api.patch(f"/runs/{run_id}", json={"name": "renamed"}).json()
    assert renamed["name"] == "renamed"
    assert renamed["tags"] == ["prod", "regression"]  # untouched
