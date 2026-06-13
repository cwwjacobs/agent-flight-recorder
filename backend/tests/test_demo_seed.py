"""The seeded demo incident (POST /demo/seed)."""

from __future__ import annotations

from app.engine.demo import CHECKPOINT_FAILURE, CHECKPOINT_SAFE, DEMO_RUN_NAME


def test_seed_creates_the_demo_incident(api):
    response = api.post("/demo/seed")
    assert response.status_code == 201
    doc = response.json()

    run = doc["run"]
    assert run["name"] == DEMO_RUN_NAME
    assert run["status"] == "failed"
    assert run["checkpoints_count"] == 2

    events = api.get(f"/runs/{run['id']}/events").json()
    types = [e["event_type"] for e in events]
    # planning model call, safe tool, side-effecting tool, failing payment tool
    assert types.count("model_call") == 1
    assert types.count("tool_call") == 3
    assert "error" in types
    # the failure arrives after the safe checkpoint
    ckpt_seqs = [e["seq"] for e in events if e["event_type"] == "checkpoint"]
    error_seq = next(e["seq"] for e in events if e["event_type"] == "error")
    assert min(ckpt_seqs) < error_seq < max(ckpt_seqs)

    charge = next(e for e in events if e["name"] == "charge_customer")
    assert charge["payload"]["policy"] == "requires_approval"
    assert charge["payload"]["status"] == "error"

    labels = [c["label"] for c in api.get(f"/runs/{run['id']}/checkpoints").json()]
    assert labels == [CHECKPOINT_SAFE, CHECKPOINT_FAILURE]


def test_seed_includes_mock_tools_replay_plan(api):
    doc = api.post("/demo/seed").json()
    replay = doc["replay"]
    assert replay["mode"] == "mock_tools"
    plan = replay["tool_plan"]
    assert plan["charge_customer"]["policy"] == "requires_approval"
    # mock_tools never executes anything — the whole point of the demo
    assert {entry["action"] for entry in plan.values()} == {"mock"}
    # successful tools carry recorded results to mock with
    assert "check_inventory" in replay["mock_results"]


def test_seed_reconstructs_pre_charge_state(api):
    doc = api.post("/demo/seed").json()
    run_id = doc["run"]["id"]
    safe_id = doc["checkpoints"]["safe"]["id"]
    state = api.get(f"/runs/{run_id}/state-at/{safe_id}").json()["state"]
    assert state["step"] == "reserved"
    assert state["reservation"]["id"] == "rsv-7841"
    assert "charge" not in state


def test_seed_works_on_free_plan_and_can_be_disabled(api, monkeypatch):
    # free plan (no AFR_PREMIUM_ENABLED): seeding and its mock_tools replay work
    assert api.post("/demo/seed").status_code == 201

    monkeypatch.setenv("AFR_DEMO_SEED_ENABLED", "false")
    assert api.post("/demo/seed").status_code == 403


def test_seed_twice_creates_two_runs(api):
    first = api.post("/demo/seed").json()["run"]["id"]
    second = api.post("/demo/seed").json()["run"]["id"]
    assert first != second


def test_run_list_enrichment_carries_error_and_event_counts(api):
    api.post("/demo/seed")
    listed = api.get("/runs").json()[0]
    assert "payment provider timed out" in listed["last_error"]
    counts = listed["event_type_counts"]
    assert counts["model_call"] == 1
    assert counts["tool_call"] == 3
    assert counts["checkpoint"] == 2
