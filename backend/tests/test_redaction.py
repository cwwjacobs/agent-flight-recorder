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


def test_token_usage_metrics_survive_redaction():
    payload = {
        "model": "gpt-x",
        "usage": {"prompt_tokens": 812, "completion_tokens": 144, "total_tokens": 956},
        "token_count": 956,
        "max_tokens": 4096,
        "access_token": "ya29.secret",
        "refresh_token": "1//refresh",
        "id_token": "eyJhbGciOi...",
        "session_token": "sess-abc",
        "token": "bare-token-is-still-a-secret",
    }
    scrubbed = default_redact(payload)
    assert scrubbed["usage"] == {"prompt_tokens": 812, "completion_tokens": 144, "total_tokens": 956}
    assert scrubbed["token_count"] == 956
    assert scrubbed["max_tokens"] == 4096
    assert scrubbed["access_token"] == REDACTED_MARKER
    assert scrubbed["refresh_token"] == REDACTED_MARKER
    assert scrubbed["id_token"] == REDACTED_MARKER
    assert scrubbed["session_token"] == REDACTED_MARKER
    assert scrubbed["token"] == REDACTED_MARKER


def test_value_level_secrets_in_free_text():
    payload = {
        "prompt": "use OPENAI key sk-proj-ABCDEFGHIJKLMNOP1234567890 then continue",
        "trace": "header was Authorization: Bearer abcdef1234567890ABCDEFmore",
        "aws": "leaked id AKIA1234567890ABCD56 in logs",
        "dsn": "postgres://user:supersecretpw@db.host:5432/app",
        "jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NSJ9.s5xYdummysig1234",
        "note": "nothing sensitive here at all",
    }
    scrubbed = default_redact(payload)
    # secrets gone
    assert "sk-proj-ABCDEFGHIJKLMNOP1234567890" not in scrubbed["prompt"]
    assert "abcdef1234567890ABCDEF" not in scrubbed["trace"]
    assert "AKIA1234567890ABCD56" not in scrubbed["aws"]
    assert "supersecretpw" not in scrubbed["dsn"]
    assert "eyJhbGciOiJIUzI1NiJ9" not in scrubbed["jwt"]
    # surrounding context preserved
    assert "use OPENAI key" in scrubbed["prompt"]
    assert REDACTED_MARKER in scrubbed["prompt"]
    assert "@db.host" in scrubbed["dsn"]
    # ordinary text untouched
    assert scrubbed["note"] == "nothing sensitive here at all"


def test_value_redaction_does_not_eat_token_usage_strings():
    # the deliberate token-telemetry carve-out must hold for string values too
    scrubbed = default_redact({"summary": "used prompt_tokens=812 total_tokens=956"})
    assert scrubbed["summary"] == "used prompt_tokens=812 total_tokens=956"


def test_value_level_redaction_covers_supported_secret_families():
    secrets = {
        "openai": "sk-proj-ABCDEFGHIJKLMNOP1234567890",
        "aws_akia": "AKIA1234567890ABCD56",
        "aws_asia": "ASIA1234567890ABCD56",
        "github_classic": "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456",
        "github_fine_grained": "github_pat_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456",
        "slack": "xoxb-1234567890-ABCDEFGHIJ",
        "google": "AIzaABCDEFGHIJKLMNOPQRSTUVWXYZ123456789",
        "jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NSJ9.s5xYdummysig1234",
        "pem": (
            "-----BEGIN PRIVATE KEY-----\n"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ\n"
            "-----END PRIVATE KEY-----"
        ),
        "bearer": "Bearer abcdef1234567890ABCDEF",
        "url": "postgres://user:supersecretpw@db.host:5432/app",
    }
    scrubbed = default_redact({key: f"before {value} after" for key, value in secrets.items()})
    for key, secret in secrets.items():
        assert secret not in scrubbed[key]
        assert REDACTED_MARKER in scrubbed[key]


def test_value_redaction_applies_at_ingest(api):
    run_id = api.post("/runs", json={}).json()["id"]
    api.post(
        f"/runs/{run_id}/events",
        json={
            "event_type": "model_call",
            "name": "ask",
            "payload": {"prompt": "the key is sk-live-ABCDEFGHIJKLMNOP1234 use it", "status": "ok"},
        },
    )
    ev = api.get(f"/runs/{run_id}/events").json()[0]
    assert "sk-live-ABCDEFGHIJKLMNOP1234" not in ev["payload"]["prompt"]
    assert REDACTED_MARKER in ev["payload"]["prompt"]
    assert ev["payload"]["status"] == "ok"
