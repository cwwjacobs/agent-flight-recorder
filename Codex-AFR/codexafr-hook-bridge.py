#!/usr/bin/env python3
"""Codex hook bridge: forwards Codex hook JSON from stdin to the AFR launcher.

This script is registered as a Codex hook command.  Codex writes a JSON
payload to stdin for each hook invocation.  We extract the relevant fields,
augment them with the AFR run id from the environment, and POST a structured
event to CODEX_AFR_EVENT_URL (a small local receiver started by codexafr).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    url = os.environ.get("CODEX_AFR_EVENT_URL")
    run_id = os.environ.get("CODEX_AFR_RUN_ID")
    if not url:
        print("codexafr-hook-bridge: CODEX_AFR_EVENT_URL not set", file=sys.stderr)
        return 0
    if not run_id:
        print("codexafr-hook-bridge: CODEX_AFR_RUN_ID not set", file=sys.stderr)
        return 0

    try:
        raw = sys.stdin.read()
        if not raw:
            payload_in = {}
        else:
            payload_in = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"codexafr-hook-bridge: invalid JSON on stdin: {exc}", file=sys.stderr)
        return 0

    if not isinstance(payload_in, dict):
        payload_in = {"raw": payload_in}

    hook_event_name = payload_in.get("hook_event_name") or payload_in.get("event")

    out = {
        "hook_event_name": hook_event_name,
        "run_id": run_id,
        "session_id": payload_in.get("session_id"),
        "turn_id": payload_in.get("turn_id"),
        "tool_name": payload_in.get("tool_name"),
        "tool_use_id": payload_in.get("tool_use_id"),
        "tool_input": payload_in.get("tool_input"),
        "tool_response": payload_in.get("tool_response"),
        "model": payload_in.get("model"),
        "cwd": payload_in.get("cwd"),
        "raw_payload": payload_in,
    }

    data = json.dumps(out).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
    except urllib.error.HTTPError as exc:
        # Non-fatal: never block Codex because of an AFR ingest issue.
        print(
            f"codexafr-hook-bridge: HTTP {exc.code} forwarding {hook_event_name}",
            file=sys.stderr,
        )
    except Exception as exc:
        print(
            f"codexafr-hook-bridge: failed to forward {hook_event_name}: {exc}",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
