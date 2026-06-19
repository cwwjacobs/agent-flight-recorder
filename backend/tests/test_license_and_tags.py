"""Feature-availability endpoint + tags/notes (opt-in) endpoints."""

from __future__ import annotations

import pytest


@pytest.fixture()
def experimental(monkeypatch):
    monkeypatch.setenv("AFR_EXPERIMENTAL_FEATURES_ENABLED", "true")


def test_features_endpoint_standard(api):
    info = api.get("/license").json()
    assert info["experimental_enabled"] is False
    assert info["features"]["recorder"] is True
    assert info["features"]["forked_replay"] is False
    assert "AFR_EXPERIMENTAL_FEATURES_ENABLED" in info["hint"]


def test_features_endpoint_experimental(experimental, api):
    info = api.get("/license").json()
    assert info["experimental_enabled"] is True
    assert info["features"]["state_diff"] is True
    assert info["hint"] is None


def test_deprecated_premium_alias_still_enables(monkeypatch, api):
    # Back-compat: the deprecated AFR_PREMIUM_ENABLED still turns features on.
    monkeypatch.setenv("AFR_PREMIUM_ENABLED", "true")
    info = api.get("/license").json()
    assert info["experimental_enabled"] is True


def test_tags_notes_gated_when_standard(api):
    run_id = api.post("/runs", json={}).json()["id"]
    r = api.patch(f"/runs/{run_id}", json={"tags": ["x"]})
    assert r.status_code == 403
    assert r.json()["detail"]["feature"] == "tags_notes"


def test_tags_notes_and_tag_filter(experimental, api):
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
