#!/usr/bin/env python3
"""Smoke test against a *running* AFR backend (stdlib only).

    python scripts/smoke.py [--api-url URL]      # or: make smoke

Walks the core loop end to end: health → license → create run → append
event → checkpoint → state reconstruction → replay request → end run. Replay
may be disabled by the operator. Exits non-zero on the first failure. Honors
AFR_API_URL and AFR_API_TOKEN.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_API_URL = "http://127.0.0.1:8700"


def call(api_url: str, method: str, path: str, body: dict | None = None) -> dict | list:
    data = json.dumps(body).encode() if body is not None else (b"" if method == "POST" else None)
    request = urllib.request.Request(f"{api_url}{path}", data=data, method=method)
    request.add_header("Content-Type", "application/json")
    token = os.environ.get("AFR_API_TOKEN", "").strip()
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    # AFR is localhost-first. Do not silently send its API traffic through
    # ambient HTTP(S)_PROXY / ALL_PROXY configuration.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=15) as response:
        return json.loads(response.read())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api-url", default=os.environ.get("AFR_API_URL", DEFAULT_API_URL))
    args = parser.parse_args()
    api_url = args.api_url.rstrip("/")

    failed = False

    def step(label: str, fn):
        nonlocal failed
        try:
            result = fn()
            print(f"  [ok]   {label}")
            return result
        except urllib.error.HTTPError as exc:
            failed = True
            print(f"  [FAIL] {label}: HTTP {exc.code} {exc.read().decode(errors='replace')[:200]}")
        except urllib.error.URLError as exc:
            failed = True
            print(f"  [FAIL] {label}: {exc.reason}")
            print(f"         is the backend running at {api_url}?  make serve  /  docker compose up")
            sys.exit(1)
        return None

    print(f"smoke test against {api_url}")
    health = step("GET /health", lambda: call(api_url, "GET", "/health"))
    if health:
        print(f"         service={health.get('service')} version={health.get('version')}")
    step("GET /license", lambda: call(api_url, "GET", "/license"))

    run = step("POST /runs", lambda: call(api_url, "POST", "/runs", {"name": "smoke-test"}))
    if run is None:
        sys.exit(1)
    run_id = run["id"]

    step(
        "POST /runs/{id}/events",
        lambda: call(api_url, "POST", f"/runs/{run_id}/events", {
            "event_type": "state_snapshot",
            "name": "state",
            "payload": {"state": {"smoke": True}, "mode": "replace"},
        }),
    )
    ckpt = step(
        "POST /runs/{id}/checkpoint",
        lambda: call(api_url, "POST", f"/runs/{run_id}/checkpoint", {"label": "smoke-ckpt"}),
    )
    if ckpt:
        state = step(
            "GET /runs/{id}/state-at/{checkpoint}",
            lambda: call(api_url, "GET", f"/runs/{run_id}/state-at/{ckpt['id']}"),
        )
        if state and state.get("state", {}).get("smoke") is not True:
            failed = True
            print("  [FAIL] checkpoint state did not round-trip")

        replay = step(
            "POST /runs/{id}/replay (mock_tools)",
            lambda: call(api_url, "POST", f"/runs/{run_id}/replay", {
                "checkpoint_id": ckpt["id"], "mode": "mock_tools",
            }),
        )
        if replay:
            replay_status = replay.get("status")
            if replay_status == "disabled":
                print("         replay is disabled by operator (safe default)")
            elif replay_status == "ready":
                if replay.get("state", {}).get("smoke") is not True:
                    failed = True
                    print("  [FAIL] replay state did not round-trip")
            else:
                failed = True
                print(f"  [FAIL] unexpected replay status: {replay_status!r}")
    step(
        "POST /runs/{id}/end",
        lambda: call(api_url, "POST", f"/runs/{run_id}/end", {"status": "completed"}),
    )

    print()
    if failed:
        sys.exit("smoke test FAILED")
    print("smoke test passed")


if __name__ == "__main__":
    main()
