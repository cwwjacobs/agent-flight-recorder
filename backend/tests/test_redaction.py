"""Redaction: default keys, nesting, custom hooks, env toggles."""

from __future__ import annotations

import pytest

from app.redaction import REDACTED_MARKER, clear_redactors, default_redact, register_redactor


def test_default_keys_are_redacted_recursively():
    payload = {
        "model": "gpt-x",
        "api_key": "sk-live-123",
        "config": {
            "OPENAI_API_KEY": "sk-456",
            "Authorization": "Bearer abc",
            "nested": [{"password": "hunter2"}, {"fine": "keep"}],
        },
        "headers": [{"x-secret-header": "shh"}],
        "output": "normal text",
    }
    scrubbed = default_redact(payload)
    assert scrubbed["api_key"] == REDACTED_MARKER
    assert scrubbed["config"]["OPENAI_API_KEY"] == REDACTED_MARKER
    assert scrubbed["config"]["Authorization"] == REDACTED_MARKER
    assert scrubbed["config"]["nested"][0]["password"] == REDACTED_MARKER
    assert scrubbed["headers"][0]["x-secret-header"] == REDACTED_MARKER
    # non-sensitive data untouched
    assert scrubbed["model"] == "gpt-x"
    assert scrubbed["output"] == "normal text"
    assert scrubbed["config"]["nested"][1]["fine"] == "keep"


def test_sensitive_subtrees_are_fully_masked():
    scrubbed = default_redact({"credentials": {"user": "a", "pass": "b"}})
    assert scrubbed["credentials"] == REDACTED_MARKER


def test_extra_keys_via_env(monkeypatch):
    monkeypatch.setenv("AFR_REDACT_KEYS", "ssn, internal_id")
    scrubbed = default_redact({"ssn": "123-45-6789", "internal_id": 9, "name": "ok"})
    assert scrubbed["ssn"] == REDACTED_MARKER
    assert scrubbed["internal_id"] == REDACTED_MARKER
    assert scrubbed["name"] == "ok"


def test_ingest_applies_redaction(api):
    run_id = api.post("/runs", json={"metadata": {"token": "tok-1", "env": "ci"}}).json()["id"]
    api.post(
        f"/runs/{run_id}/events",
        json={
            "event_type": "tool_call",
            "name": "http_post",
            "payload": {"args": {"authorization": "Bearer xyz"}, "result": "ok", "status": "ok"},
        },
    )
    api.post(f"/runs/{run_id}/checkpoint", json={"state": {"session_token": "s3cr3t", "step": 2}})

    run = api.get(f"/runs/{run_id}").json()
    assert run["metadata"]["token"] == REDACTED_MARKER
    assert run["metadata"]["env"] == "ci"

    events = api.get(f"/runs/{run_id}/events").json()
    tool = next(e for e in events if e["event_type"] == "tool_call")
    assert tool["payload"]["args"]["authorization"] == REDACTED_MARKER

    ckpt = api.get(f"/runs/{run_id}/checkpoints").json()[0]
    state = api.get(f"/runs/{run_id}/state-at/{ckpt['id']}").json()["state"]
    assert state["session_token"] == REDACTED_MARKER
    assert state["step"] == 2


def test_redaction_can_be_disabled(monkeypatch, api):
    monkeypatch.setenv("AFR_REDACTION_ENABLED", "false")
    run_id = api.post("/runs", json={"metadata": {"token": "visible"}}).json()["id"]
    assert api.get(f"/runs/{run_id}").json()["metadata"]["token"] == "visible"


def test_custom_redactor_premium_only(monkeypatch, api):
    @register_redactor
    def drop_emails(payload: dict) -> dict:
        return {k: ("[EMAIL]" if k == "email" else v) for k, v in payload.items()}

    try:
        # free mode: custom redactor not applied
        run_id = api.post("/runs", json={}).json()["id"]
        api.post(
            f"/runs/{run_id}/events",
            json={"event_type": "log", "payload": {"email": "a@b.c", "message": "hi"}},
        )
        ev = api.get(f"/runs/{run_id}/events").json()[0]
        assert ev["payload"]["email"] == "a@b.c"

        # premium: applied
        monkeypatch.setenv("AFR_PREMIUM_ENABLED", "true")
        api.post(
            f"/runs/{run_id}/events",
            json={"event_type": "log", "payload": {"email": "a@b.c", "message": "hi"}},
        )
        ev = api.get(f"/runs/{run_id}/events").json()[-1]
        assert ev["payload"]["email"] == "[EMAIL]"
    finally:
        clear_redactors()
