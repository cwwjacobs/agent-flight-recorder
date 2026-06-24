"""afr — the Agent Flight Recorder CLI.

    afr doctor [--read-only]          check backend, license, auth, SDK setup
    afr init                          write .afr/config.json in the cwd
    afr runs list [--status S]        list recorded runs
    afr runs show <run_id>            run details + checkpoints
    afr events <run_id> [--type T]    print a run's timeline
    afr replay <run_id> --from <ckpt> [--mode M] [--handler module:fn]
    afr export <run_id> [-o FILE]     export a portable JSON bundle
    afr regression-case <run_id> --from <ckpt> -o <dir>
                                      template a regression case from a checkpoint

Run and checkpoint ids accept unique prefixes (first 8 chars are plenty).
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import httpx

import afr as afr_sdk
from afr.client import AFRAPIError, AFRClient
from afr.hooks import replay as sdk_replay
from afr.types import DEFAULT_API_URL, resolve_api_url

CONFIG_DIR = ".afr"
CONFIG_FILE = "config.json"


# ---------------------------------------------------------------------------
# config + client


def load_config() -> dict[str, Any]:
    path = Path.cwd() / CONFIG_DIR / CONFIG_FILE
    if path.is_file():
        try:
            return json.loads(path.read_text())
        except ValueError:
            print(f"warning: could not parse {path}, ignoring", file=sys.stderr)
    return {}


def make_client(args: argparse.Namespace) -> AFRClient:
    api_url, _ = resolve_api_url_with_source(args)
    return AFRClient(api_url)


def resolve_api_url_with_source(args: argparse.Namespace) -> tuple[str, str]:
    """The URL the CLI will talk to, plus where it came from (for doctor)."""
    if args.api_url:
        return args.api_url, "--api-url flag"
    config_url = load_config().get("api_url")
    if config_url:
        return config_url, ".afr/config.json"
    if os.environ.get("AFR_API_URL"):
        return os.environ["AFR_API_URL"], "AFR_API_URL env"
    return DEFAULT_API_URL, "default"


# ---------------------------------------------------------------------------
# output helpers


def emit_json(data: Any) -> None:
    print(json.dumps(data, indent=2, default=str))


def short(value: str | None, n: int = 8) -> str:
    return (value or "")[:n]


def fmt_ts(ts: str | None) -> str:
    if not ts:
        return "-"
    return ts.replace("T", " ")[:19]


def table(headers: list[str], rows: list[list[str]]) -> None:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(line)
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))


def trunc(value: Any, n: int = 60) -> str:
    text = json.dumps(value, default=str) if not isinstance(value, str) else value
    return text if len(text) <= n else text[: n - 1] + "…"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def replay_env_enabled() -> bool:
    return os.environ.get("AFR_REPLAY_ENABLED", "").strip().lower() in (
        "true",
        "1",
        "yes",
        "on",
    )


def safe_py_identifier(value: str) -> str:
    name = re.sub(r"\W+", "_", value).strip("_").lower()
    return name or "run"


def count_events_by_type(events: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        event_type = str(event.get("event_type") or "unknown")
        counts[event_type] = counts.get(event_type, 0) + 1
    return dict(sorted(counts.items()))


def summarize_replay_ticket(ticket: dict[str, Any] | None, attempted: bool) -> dict[str, Any]:
    if not attempted:
        return {
            "attempted": False,
            "generated": False,
            "reason": "AFR_REPLAY_ENABLED is not true; dry-run replay ticket was not requested.",
        }
    if not isinstance(ticket, dict):
        return {
            "attempted": True,
            "generated": False,
            "reason": "Replay request returned a non-object response.",
        }
    status = ticket.get("status")
    return {
        "attempted": True,
        "generated": status == "ready",
        "run_id": ticket.get("run_id"),
        "checkpoint_id": ticket.get("checkpoint_id"),
        "label": ticket.get("label"),
        "mode": ticket.get("mode"),
        "status": status,
        "replay_event_id": ticket.get("replay_event_id"),
        "message": ticket.get("message"),
    }


# ---------------------------------------------------------------------------
# id resolution (accept unique prefixes)


def resolve_run_id(client: AFRClient, prefix: str) -> str:
    if len(prefix) >= 32:
        return prefix
    matches = [r["id"] for r in client.list_runs(limit=500) if r["id"].startswith(prefix)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        sys.exit(f"error: no run matches id prefix {prefix!r}")
    sys.exit(f"error: ambiguous run id prefix {prefix!r} ({len(matches)} matches)")


def resolve_checkpoint_id(client: AFRClient, run_id: str, prefix: str) -> str:
    if len(prefix) >= 32:
        return prefix
    matches = [
        c["id"] for c in client.list_checkpoints(run_id) if c["id"].startswith(prefix)
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        sys.exit(f"error: no checkpoint in run {short(run_id)} matches prefix {prefix!r}")
    sys.exit(f"error: ambiguous checkpoint prefix {prefix!r} ({len(matches)} matches)")


# ---------------------------------------------------------------------------
# commands


def cmd_init(args: argparse.Namespace) -> None:
    config_dir = Path.cwd() / CONFIG_DIR
    config_dir.mkdir(exist_ok=True)
    config_path = config_dir / CONFIG_FILE
    config = {"api_url": args.api_url or DEFAULT_API_URL}
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    print(f"wrote {config_path}")
    print(f"  api_url: {config['api_url']}")
    print()
    print("next steps:")
    print("  1. start the backend:  cd backend && python -m app")
    print("  2. record a run:       python examples/toy_agent/toy_agent.py")
    print("  3. inspect it:         afr runs list")


def cmd_runs_list(args: argparse.Namespace) -> None:
    with make_client(args) as client:
        runs = client.list_runs(status=args.status, tag=args.tag, limit=args.limit)
    if args.json:
        emit_json(runs)
        return
    if not runs:
        print("no runs recorded yet")
        return
    table(
        ["ID", "NAME", "STATUS", "STARTED", "EVENTS", "CKPTS", "TAGS"],
        [
            [
                short(r["id"]),
                trunc(r["name"], 32),
                r["status"],
                fmt_ts(r["created_at"]),
                str(r.get("events_count", 0)),
                str(r.get("checkpoints_count", 0)),
                ",".join(r.get("tags") or []) or "-",
            ]
            for r in runs
        ],
    )


def cmd_runs_show(args: argparse.Namespace) -> None:
    with make_client(args) as client:
        run_id = resolve_run_id(client, args.run_id)
        run = client.get_run(run_id)
        checkpoints = client.list_checkpoints(run_id)
    if args.json:
        emit_json({"run": run, "checkpoints": checkpoints})
        return
    print(f"run       {run['id']}")
    print(f"name      {run['name']}")
    print(f"status    {run['status']}")
    print(f"started   {fmt_ts(run['created_at'])}")
    print(f"ended     {fmt_ts(run.get('ended_at'))}")
    print(f"events    {run.get('events_count', 0)}")
    if run.get("tags"):
        print(f"tags      {', '.join(run['tags'])}")
    if run.get("notes"):
        print(f"notes     {trunc(run['notes'], 100)}")
    if run.get("parent_run_id"):
        print(f"forked    from {short(run['parent_run_id'])} @ {short(run.get('fork_checkpoint_id'))}")
    if run.get("forks"):
        print(f"forks     {', '.join(short(f['id']) for f in run['forks'])}")
    if run.get("metadata"):
        print(f"metadata  {trunc(run['metadata'], 100)}")
    if checkpoints:
        print()
        print("checkpoints:")
        table(
            ["ID", "LABEL", "AT", "SEQ"],
            [
                [short(c["id"]), c.get("label") or "-", fmt_ts(c["created_at"]), str(c["event_seq"])]
                for c in checkpoints
            ],
        )


def cmd_events(args: argparse.Namespace) -> None:
    with make_client(args) as client:
        run_id = resolve_run_id(client, args.run_id)
        events = client.list_events(run_id, event_type=args.type, limit=args.limit)
    if args.errors_only:
        events = [
            e
            for e in events
            if e["event_type"] == "error" or (e.get("payload") or {}).get("status") == "error"
        ]
    if args.json:
        emit_json(events)
        return
    if not events:
        print("no events")
        return
    rows = []
    for e in events:
        payload = e.get("payload") or {}
        status = payload.get("status", "")
        marker = "✗" if (e["event_type"] == "error" or status == "error") else " "
        rows.append(
            [
                str(e["seq"]),
                marker,
                fmt_ts(e["created_at"]),
                e["event_type"],
                e.get("name") or "-",
                trunc(payload, 70),
            ]
        )
    table(["SEQ", "!", "TIME", "TYPE", "NAME", "PAYLOAD"], rows)


def cmd_replay(args: argparse.Namespace) -> None:
    with make_client(args) as client:
        run_id = resolve_run_id(client, args.run_id)
        checkpoint_id = resolve_checkpoint_id(client, run_id, args.from_checkpoint)
        result = sdk_replay(
            run_id,
            checkpoint_id,
            mode=args.mode,
            client=client,
            handler=args.handler,
            approved=args.approved,
        )
    if args.json:
        emit_json(result)
        return
    if result.get("disabled"):
        print(f"replay disabled for run {short(run_id)}: {result.get('reason')}")
        return
    ticket = result["ticket"]
    print(f"replay ticket for run {short(run_id)} @ checkpoint {short(checkpoint_id)}")
    print(f"  label   : {ticket.get('label') or '-'}")
    print(f"  mode    : {ticket.get('mode')}")
    print(f"  status  : {ticket.get('status')}")
    if ticket.get("tool_plan"):
        print("  tool plan:")
        for tool, plan in ticket["tool_plan"].items():
            print(f"    - {tool}: {plan.get('action')} (policy: {plan.get('policy')})")
    print("  state   :")
    print(_indent(json.dumps(ticket.get("state") or {}, indent=2), 4))
    if result["handler_invoked"]:
        print(f"  handler returned: {trunc(result['handler_result'], 200)}")
    elif args.mode == "dry_run":
        print("  (dry_run: no resume handler invoked)")
    elif not args.handler:
        print("  (no handler given — pass --handler module:function to resume your agent)")


def cmd_fork(args: argparse.Namespace) -> None:
    with make_client(args) as client:
        run_id = resolve_run_id(client, args.run_id)
        checkpoint_id = resolve_checkpoint_id(client, run_id, args.from_checkpoint)
        fork = client.fork(run_id, checkpoint_id, name=args.name)
    if args.json:
        emit_json(fork)
        return
    print(f"forked run {short(run_id)} @ {short(checkpoint_id)}")
    print(f"  new run : {fork['id']}")
    print(f"  name    : {fork['name']}")
    print(f"  inspect : afr runs show {short(fork['id'])}")


def cmd_tag(args: argparse.Namespace) -> None:
    with make_client(args) as client:
        run_id = resolve_run_id(client, args.run_id)
        run = client.get_run(run_id)
        tags = set(run.get("tags") or [])
        if args.remove:
            tags -= set(args.tags)
        else:
            tags |= set(args.tags)
        updated = client.update_run(run_id, tags=sorted(tags))
    if args.json:
        emit_json(updated)
        return
    print(f"run {short(run_id)} tags: {', '.join(updated.get('tags') or []) or '(none)'}")


def cmd_note(args: argparse.Namespace) -> None:
    with make_client(args) as client:
        run_id = resolve_run_id(client, args.run_id)
        if args.append:
            existing = client.get_run(run_id).get("notes") or ""
            text = (existing + "\n" + args.text).strip()
        else:
            text = args.text
        client.update_run(run_id, notes=text)
    print(f"run {short(run_id)} notes updated")


def cmd_license(args: argparse.Namespace) -> None:
    with make_client(args) as client:
        info = client.get_license()
    if args.json:
        emit_json(info)
        return
    print(f"plan: {info['plan']}")
    for feature, enabled in info["features"].items():
        print(f"  {'✓' if enabled else '✗'} {feature}")
    if info.get("hint"):
        print(f"\n{info['hint']}")


def cmd_export(args: argparse.Namespace) -> None:
    with make_client(args) as client:
        run_id = resolve_run_id(client, args.run_id)
        bundle = client.export_bundle(run_id)
    out = args.output or f"afr-export-{short(run_id)}.json"
    Path(out).write_text(json.dumps(bundle, indent=2, default=str) + "\n")
    print(f"exported run {short(run_id)} → {out}")
    print(
        f"  {len(bundle['events'])} events, {len(bundle['checkpoints'])} checkpoints"
    )


def cmd_regression_case(args: argparse.Namespace) -> None:
    output_dir = Path(args.output)
    with make_client(args) as client:
        run_id = resolve_run_id(client, args.run_id)
        checkpoint_id = resolve_checkpoint_id(client, run_id, args.from_checkpoint)
        bundle = client.export_bundle(run_id)
        state_doc = client.state_at(run_id, checkpoint_id, reconstruct=True)

        replay_attempted = replay_env_enabled()
        replay_ticket = (
            client.replay(run_id, checkpoint_id, mode="dry_run") if replay_attempted else None
        )

    run = bundle["run"]
    events = bundle["events"]
    checkpoints = bundle["checkpoints"]
    checkpoint = next((c for c in checkpoints if c["id"] == checkpoint_id), None)
    run_prefix = short(run_id)
    checkpoint_prefix = short(checkpoint_id)
    case = {
        "format": "afr.regression_case.v1",
        "generated_at": utc_now(),
        "run": {
            "id": run.get("id"),
            "prefix": run_prefix,
            "name": run.get("name"),
            "status": run.get("status"),
            "created_at": run.get("created_at"),
            "ended_at": run.get("ended_at"),
            "metadata": run.get("metadata") or {},
        },
        "checkpoint": {
            "id": checkpoint_id,
            "prefix": checkpoint_prefix,
            "label": (checkpoint or state_doc.get("checkpoint") or {}).get("label"),
            "event_seq": (checkpoint or state_doc.get("checkpoint") or {}).get("event_seq"),
            "created_at": (checkpoint or state_doc.get("checkpoint") or {}).get("created_at"),
        },
        "expected_reconstructed_state": {
            "available": "state" in state_doc,
            "state": state_doc.get("state"),
            "source": "state_at(reconstruct=True)",
        },
        "event_counts": {
            "total": len(events),
            "by_type": count_events_by_type(events),
            "checkpoints": len(checkpoints),
        },
        "source_export_summary": {
            "format": bundle.get("format"),
            "run_id": run.get("id"),
            "run_status": run.get("status"),
            "events": len(events),
            "checkpoints": len(checkpoints),
        },
        "replay_ticket_reference": summarize_replay_ticket(
            replay_ticket, attempted=replay_attempted
        ),
        "commands_used": [
            f"afr export {run_prefix} -o <export.json>",
            f"afr regression-case {run_prefix} --from {checkpoint_prefix} -o {output_dir}",
        ],
    }
    if replay_attempted:
        case["commands_used"].append(
            f"AFR_REPLAY_ENABLED=true afr --json replay {run_prefix} --from {checkpoint_prefix} --mode dry_run"
        )
    else:
        case["commands_used"].append(
            f"AFR_REPLAY_ENABLED=true afr --json replay {run_prefix} --from {checkpoint_prefix} --mode dry_run  # optional ticket reference"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    case_path = output_dir / "case.json"
    test_path = output_dir / f"test_regression_{safe_py_identifier(run_prefix)}.py"
    readme_path = output_dir / "README.md"

    case_path.write_text(json.dumps(case, indent=2, default=str) + "\n")
    test_path.write_text(_regression_case_test_template(run_prefix))
    readme_path.write_text(_regression_case_readme(case))

    summary = {
        "case_dir": str(output_dir),
        "case_json": str(case_path),
        "test_template": str(test_path),
        "readme": str(readme_path),
        "run_id": run_id,
        "checkpoint_id": checkpoint_id,
        "replay_ticket_generated": case["replay_ticket_reference"].get("generated", False),
    }
    if args.json:
        emit_json(summary)
        return
    print(f"wrote regression case template to {output_dir}")
    print(f"  case      : {case_path}")
    print(f"  pytest    : {test_path}")
    print(f"  readme    : {readme_path}")
    ref = case["replay_ticket_reference"]
    if summary["replay_ticket_generated"]:
        print(f"  replay    : {ref.get('status')} ticket {short(ref.get('replay_event_id'))}")
    elif ref.get("attempted"):
        print(f"  replay    : {ref.get('status') or 'not ready'} ticket not generated")
    else:
        print("  replay    : skipped (set AFR_REPLAY_ENABLED=true to request a dry-run ticket)")


def _regression_case_test_template(run_prefix: str) -> str:
    test_name = safe_py_identifier(run_prefix)
    return f'''"""AFR regression-case template.

This file is generated scaffolding. It does not execute your agent until you
replace the TODO section with your own resume or agent entrypoint.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


CASE_PATH = Path(__file__).with_name("case.json")


def load_case() -> dict:
    return json.loads(CASE_PATH.read_text())


def test_regression_{test_name}_case_shape() -> None:
    case = load_case()
    assert case["format"] == "afr.regression_case.v1"
    assert case["run"]["id"]
    assert case["checkpoint"]["id"]
    assert "state" in case["expected_reconstructed_state"]


def test_regression_{test_name}_user_resume_hook() -> None:
    case = load_case()
    expected_state = case["expected_reconstructed_state"]["state"]

    pytest.skip(
        "TODO: import your agent/resume function, start it from expected_state, "
        "and assert the behavior you want this regression case to protect."
    )

    # Example shape after wiring your code:
    # from my_agent import resume_from_state
    # result = resume_from_state(expected_state)
    # assert result == <your expected outcome>
'''


def _regression_case_readme(case: dict[str, Any]) -> str:
    run = case["run"]
    checkpoint = case["checkpoint"]
    replay_ref = case["replay_ticket_reference"]
    replay_note = (
        f"A dry-run replay ticket was requested and returned status `{replay_ref.get('status')}`."
        if replay_ref.get("attempted")
        else "Replay was not requested because `AFR_REPLAY_ENABLED` was not true in the CLI environment."
    )
    return f"""# AFR Regression Case Template

Run: `{run['id']}` (`{run.get('name')}`)

Checkpoint: `{checkpoint['id']}` (`{checkpoint.get('label') or 'unlabeled'}`)

## Commands Used

```bash
{chr(10).join(case['commands_used'])}
```

## What This Case Verifies

- The source run can be exported as an AFR JSON bundle.
- The checkpoint can be resolved from the run.
- AFR can reconstruct the expected checkpoint state from recorded events and snapshots.
- Event and checkpoint counts are captured for later drift checks.

## What Remains User-Supplied

- Importing your agent or resume function.
- Starting that function from the expected reconstructed state in `case.json`.
- Asserting the domain-specific behavior that should not regress.

The generated pytest file intentionally skips the resume test until you replace
the TODO with your own hook. It does not claim to execute your agent.

## Replay And Export Notes

{replay_note}

Replay is opt-in and ticket-based. The backend prepares a ticket; it does not
execute user code. This case uses JSON export data only and does not claim JSONL export support.
"""


def run_doctor(client: AFRClient, api_url: str, url_source: str, read_only: bool) -> bool:
    """All doctor checks against an already-built client. Returns overall ok."""
    ok = True
    token_set = bool(os.environ.get("AFR_API_TOKEN", "").strip())
    print("afr doctor")
    print(f"  sdk version : {afr_sdk.__version__}")
    print(f"  api url     : {api_url}  (from {url_source})")
    print(f"  auth token  : {'configured via AFR_API_TOKEN' if token_set else 'not configured (AFR_API_TOKEN unset)'}")
    print()

    try:
        health = client.health()
        print(f"  [ok]   backend reachable — {health.get('service')} v{health.get('version')}")
    except (httpx.ConnectError, httpx.ConnectTimeout):
        print(f"  [FAIL] backend unreachable at {api_url}")
        print("         start it locally :  make serve")
        print("         or via docker    :  docker compose up --build")
        if api_url.rstrip("/") != DEFAULT_API_URL:
            print(f"         docker default   :  afr -A {DEFAULT_API_URL} doctor")
        print("         elsewhere        :  afr -A http://host:8700 doctor   (or set AFR_API_URL)")
        return False
    except (AFRAPIError, httpx.HTTPError) as exc:
        print(f"  [FAIL] /health failed: {exc}")
        return False

    try:
        info = client.get_license()
        plan = info.get("plan", "?")
        print(f"  [ok]   license: {plan} plan"
              + ("" if plan == "premium" else "  (premium off — set AFR_PREMIUM_ENABLED=true to compare)"))
    except (AFRAPIError, httpx.HTTPError) as exc:
        ok = False
        print(f"  [FAIL] /license failed: {exc}")

    try:
        client.list_runs(limit=1)
        print("  [ok]   read access (/runs)")
    except AFRAPIError as exc:
        ok = False
        if exc.status_code == 401:
            hint = (
                "token is wrong — it must match the server's AFR_API_TOKEN"
                if token_set
                else "server requires a token — export AFR_API_TOKEN=<server token>"
            )
            print(f"  [FAIL] read access denied (401): {hint}")
        else:
            print(f"  [FAIL] read access failed: {exc}")
    except httpx.HTTPError as exc:
        ok = False
        print(f"  [FAIL] read access failed: {exc}")

    if read_only:
        print("  [skip] write check (--read-only)")
    else:
        try:
            run = client.create_run(name="afr-doctor-check", metadata={"doctor": True})
            client.append_event(run["id"], "log", name="doctor", payload={"message": "doctor write check"})
            client.end_run(run["id"], status="completed")
            print(f"  [ok]   write access — created + ended test run {short(run['id'])}")
        except (AFRAPIError, httpx.HTTPError) as exc:
            ok = False
            print(f"  [FAIL] write check failed: {exc}")

    print()
    print("all checks passed — record something: make demo" if ok else "doctor found problems (see above)")
    return ok


def cmd_doctor(args: argparse.Namespace) -> None:
    api_url, url_source = resolve_api_url_with_source(args)
    with AFRClient(api_url) as client:
        ok = run_doctor(client, api_url, url_source, read_only=args.read_only)
    if not ok:
        sys.exit(1)


def _indent(text: str, n: int) -> str:
    pad = " " * n
    return "\n".join(pad + line for line in text.splitlines())


# ---------------------------------------------------------------------------
# parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="afr",
        description="Agent Flight Recorder — inspect and replay recorded agent runs",
    )
    parser.add_argument("-A", "--api-url", help="backend URL (default: $AFR_API_URL or .afr/config.json)")
    parser.add_argument("--json", action="store_true", help="emit raw JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    p_doctor = sub.add_parser("doctor", help="check backend reachability, license, auth, and setup")
    p_doctor.add_argument("--read-only", action="store_true", help="skip the test-run write check")
    p_doctor.set_defaults(func=cmd_doctor)

    p_init = sub.add_parser("init", help="write .afr/config.json for this project")
    p_init.set_defaults(func=cmd_init)

    p_runs = sub.add_parser("runs", help="list and inspect runs")
    runs_sub = p_runs.add_subparsers(dest="runs_command", required=True)

    p_list = runs_sub.add_parser("list", help="list runs")
    p_list.add_argument("--status", choices=["running", "completed", "failed"])
    p_list.add_argument("--tag", help="filter by tag (premium)")
    p_list.add_argument("--limit", type=int, default=50)
    p_list.set_defaults(func=cmd_runs_list)

    p_show = runs_sub.add_parser("show", help="show one run")
    p_show.add_argument("run_id")
    p_show.set_defaults(func=cmd_runs_show)

    p_events = sub.add_parser("events", help="print a run's event timeline")
    p_events.add_argument("run_id")
    p_events.add_argument("--type", help="filter by event type")
    p_events.add_argument("--errors-only", action="store_true", help="failed/error events only")
    p_events.add_argument("--limit", type=int, default=1000)
    p_events.set_defaults(func=cmd_events)

    p_replay = sub.add_parser("replay", help="replay a run from a checkpoint")
    p_replay.add_argument("run_id")
    p_replay.add_argument("--from", dest="from_checkpoint", required=True, metavar="CHECKPOINT")
    p_replay.add_argument(
        "--mode",
        default="dry_run",
        choices=["dry_run", "mock_tools", "allow_safe_tools", "allow_side_effects"],
        help="replay safety mode (default: dry_run; allow_* modes are premium)",
    )
    p_replay.add_argument(
        "--approved",
        action="store_true",
        help="approve requires_approval tools (allow_side_effects mode only)",
    )
    p_replay.add_argument(
        "--handler",
        help="resume handler as 'package.module:function' (invoked unless --mode dry_run)",
    )
    p_replay.set_defaults(func=cmd_replay)

    p_fork = sub.add_parser("fork", help="fork a new run from a checkpoint (premium)")
    p_fork.add_argument("run_id")
    p_fork.add_argument("--from", dest="from_checkpoint", required=True, metavar="CHECKPOINT")
    p_fork.add_argument("--name", help="name for the forked run")
    p_fork.set_defaults(func=cmd_fork)

    p_tag = sub.add_parser("tag", help="add/remove run tags (premium)")
    p_tag.add_argument("run_id")
    p_tag.add_argument("tags", nargs="+", metavar="TAG")
    p_tag.add_argument("--remove", action="store_true", help="remove instead of add")
    p_tag.set_defaults(func=cmd_tag)

    p_note = sub.add_parser("note", help="set run notes (premium)")
    p_note.add_argument("run_id")
    p_note.add_argument("text")
    p_note.add_argument("--append", action="store_true", help="append instead of replace")
    p_note.set_defaults(func=cmd_note)

    p_license = sub.add_parser("license", help="show plan and feature flags")
    p_license.set_defaults(func=cmd_license)

    p_export = sub.add_parser("export", help="export a run as a JSON bundle")
    p_export.add_argument("run_id")
    p_export.add_argument("-o", "--output", help="output file path")
    p_export.set_defaults(func=cmd_export)

    p_regression = sub.add_parser(
        "regression-case",
        help="template a pytest regression case from a checkpoint",
    )
    p_regression.add_argument("run_id")
    p_regression.add_argument(
        "--from", dest="from_checkpoint", required=True, metavar="CHECKPOINT"
    )
    p_regression.add_argument(
        "-o", "--output", required=True, help="output directory for generated files"
    )
    p_regression.set_defaults(func=cmd_regression_case)

    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except AFRAPIError as exc:
        sys.exit(f"error: {exc}")
    except httpx.ConnectError:
        sys.exit("error: cannot reach the AFR backend — is it running? (afr -A to set the URL)")
    except httpx.HTTPError as exc:
        sys.exit(f"error: request failed: {exc}")
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
