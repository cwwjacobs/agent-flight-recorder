"""Forked replay: lineage, state seeding, gating."""

from __future__ import annotations

import pytest


@pytest.fixture()
def premium(monkeypatch):
    monkeypatch.setenv("AFR_PREMIUM_ENABLED", "true")


def _run_with_checkpoint(api) -> tuple[str, str]:
    run_id = api.post("/runs", json={"name": "parent"}).json()["id"]
    api.post(
        f"/runs/{run_id}/events",
        json={"event_type": "state_snapshot", "payload": {"state": {"step": 3, "x": "y"}}},
    )
    ckpt = api.post(f"/runs/{run_id}/checkpoint", json={"label": "branch-point"}).json()
    api.post(
        f"/runs/{run_id}/events",
        json={"event_type": "state_snapshot", "payload": {"state": {"step": 4}, "mode": "merge"}},
    )
    return run_id, ckpt["id"]


def test_fork_requires_premium(api):
    run_id, ckpt_id = _run_with_checkpoint(api)
    r = api.post(f"/runs/{run_id}/fork", json={"checkpoint_id": ckpt_id})
    assert r.status_code == 402


def test_fork_creates_linked_run_with_checkpoint_state(premium, api):
    run_id, ckpt_id = _run_with_checkpoint(api)

    r = api.post(f"/runs/{run_id}/fork", json={"checkpoint_id": ckpt_id, "name": "what-if"})
    assert r.status_code == 201
    fork = r.json()
    assert fork["name"] == "what-if"
    assert fork["parent_run_id"] == run_id
    assert fork["fork_checkpoint_id"] == ckpt_id
    assert fork["status"] == "running"

    # fork timeline starts from the checkpoint state (not the later step:4)
    events = api.get(f"/runs/{fork['id']}/events").json()
    seed = next(e for e in events if e["event_type"] == "state_snapshot")
    assert seed["payload"]["state"] == {"step": 3, "x": "y"}

    # continuing the fork diverges it from the parent
    api.post(
        f"/runs/{fork['id']}/events",
        json={"event_type": "state_snapshot", "payload": {"state": {"step": 99}, "mode": "merge"}},
    )
    fork_ckpt = api.post(f"/runs/{fork['id']}/checkpoint", json={"label": "diverged"}).json()
    state = api.get(f"/runs/{fork['id']}/state-at/{fork_ckpt['id']}").json()["state"]
    assert state == {"step": 99, "x": "y"}

    # parent lists the fork
    parent = api.get(f"/runs/{run_id}").json()
    assert [f["id"] for f in parent["forks"]] == [fork["id"]]


def test_fork_rejects_foreign_checkpoint(premium, api):
    run_id, _ = _run_with_checkpoint(api)
    other_id, other_ckpt = _run_with_checkpoint(api)
    assert other_id != run_id
    r = api.post(f"/runs/{run_id}/fork", json={"checkpoint_id": other_ckpt})
    assert r.status_code == 404
