"""API smoke: the full MVP flow over HTTP."""

from __future__ import annotations


def test_full_run_flow(api):
    # create
    r = api.post("/runs", json={"name": "api-smoke", "metadata": {"env": "test"}})
    assert r.status_code == 201
    run = r.json()
    run_id = run["id"]
    assert run["status"] == "running"

    # events
    r = api.post(
        f"/runs/{run_id}/events",
        json={"event_type": "model_call", "name": "ask", "payload": {"model": "x", "status": "ok"}},
    )
    assert r.status_code == 201
    r = api.post(
        f"/runs/{run_id}/events",
        json={"event_type": "state_snapshot", "payload": {"state": {"step": 1}}},
    )
    assert r.status_code == 201

    # checkpoint
    r = api.post(f"/runs/{run_id}/checkpoint", json={"label": "mid"})
    assert r.status_code == 201
    ckpt = r.json()
    assert ckpt["label"] == "mid"

    # state-at
    r = api.get(f"/runs/{run_id}/state-at/{ckpt['id']}")
    assert r.status_code == 200
    assert r.json()["state"] == {"step": 1}

    # replay (dry run)
    r = api.post(f"/runs/{run_id}/replay", json={"checkpoint_id": ckpt["id"]})
    assert r.status_code == 200
    ticket = r.json()
    assert ticket["status"] == "ready"
    assert ticket["state"] == {"step": 1}
    assert ticket["mode"] == "dry_run"

    # end
    r = api.post(f"/runs/{run_id}/end", json={"status": "completed"})
    assert r.status_code == 200
    assert r.json()["status"] == "completed"

    # listings
    runs = api.get("/runs").json()
    assert any(x["id"] == run_id for x in runs)
    events = api.get(f"/runs/{run_id}/events").json()
    # model_call, state_snapshot, checkpoint, replay_requested log
    types = [e["event_type"] for e in events]
    assert types.count("checkpoint") == 1
    assert "model_call" in types
    detail = api.get(f"/runs/{run_id}").json()
    assert detail["events_count"] == len(events)

    # filtered events
    only_models = api.get(f"/runs/{run_id}/events", params={"event_type": "model_call"}).json()
    assert {e["event_type"] for e in only_models} == {"model_call"}


def test_404s(api):
    assert api.get("/runs/nope").status_code == 404
    assert api.post("/runs/nope/events", json={"event_type": "log"}).status_code == 404
    assert api.post("/runs/nope/replay", json={"checkpoint_id": "x"}).status_code == 404

    run_id = api.post("/runs", json={}).json()["id"]
    assert api.get(f"/runs/{run_id}/state-at/missing").status_code == 404


def test_event_type_validation(api):
    run_id = api.post("/runs", json={}).json()["id"]
    r = api.post(f"/runs/{run_id}/events", json={"event_type": "not_a_type"})
    assert r.status_code == 422


def test_api_prefix_mirror(api):
    """The /api-prefixed mirror used by the web UI serves the same data."""
    run_id = api.post("/api/runs", json={"name": "via-prefix"}).json()["id"]
    assert api.get(f"/api/runs/{run_id}").status_code == 200
    assert api.get(f"/runs/{run_id}").status_code == 200
