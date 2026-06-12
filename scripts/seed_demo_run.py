#!/usr/bin/env python3
"""Seed the demo incident (checkout-agent-payment-timeout) over HTTP.

Talks to a *running* AFR backend — no SDK install needed, stdlib only:

    python scripts/seed_demo_run.py                       # http://127.0.0.1:8700
    python scripts/seed_demo_run.py --api-url http://host:8700
    AFR_API_TOKEN=... python scripts/seed_demo_run.py     # token-protected server

Prints the created run id and the URL to open.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_API_URL = "http://127.0.0.1:8700"


def post_seed(api_url: str, token: str | None) -> dict:
    request = urllib.request.Request(f"{api_url}/demo/seed", data=b"", method="POST")
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--api-url",
        default=os.environ.get("AFR_API_URL", DEFAULT_API_URL),
        help=f"backend URL (default: $AFR_API_URL or {DEFAULT_API_URL})",
    )
    args = parser.parse_args()
    api_url = args.api_url.rstrip("/")
    token = os.environ.get("AFR_API_TOKEN") or None

    try:
        result = post_seed(api_url, token)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        if exc.code == 401:
            sys.exit("error: server requires a token — set AFR_API_TOKEN and retry")
        if exc.code == 403:
            sys.exit(f"error: demo seeding is disabled on this server: {detail}")
        if exc.code == 404:
            sys.exit(
                "error: this backend has no /demo/seed endpoint — "
                "rebuild/update the server (docker compose up --build)"
            )
        sys.exit(f"error: HTTP {exc.code}: {detail}")
    except urllib.error.URLError as exc:
        sys.exit(
            f"error: cannot reach {api_url} ({exc.reason})\n"
            "  is the backend running?  make serve   or   docker compose up --build"
        )

    run = result["run"]
    plan = (result.get("replay") or {}).get("tool_plan", {})
    print(f"seeded demo run: {run['name']}")
    print(f"  run id      : {run['id']}")
    print(f"  status      : {run['status']}")
    print(f"  events      : {run['events_count']}")
    print(f"  checkpoints : {run['checkpoints_count']}")
    if plan:
        print("  replay plan (mock_tools):")
        for tool, entry in plan.items():
            print(f"    - {tool}: {entry['action']} (policy: {entry['policy']})")
    print()
    print(f"open the incident:  {api_url}/#/runs/{run['id']}")
    print(f"or via CLI:         afr runs show {run['id'][:8]}")


if __name__ == "__main__":
    main()
