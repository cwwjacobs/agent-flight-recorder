"""afr — the Agent Flight Recorder CLI.

    afr init                          write .afr/config.json in the cwd
    afr runs list [--status S]        list recorded runs
    afr runs show <run_id>            run details + checkpoints
    afr events <run_id> [--type T]    print a run's timeline
    afr replay <run_id> --from <ckpt> [--mode M] [--handler module:fn]
    afr export <run_id> [-o FILE]     export a portable JSON bundle

Run and checkpoint ids accept unique prefixes (first 8 chars are plenty).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import httpx

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
    api_url = args.api_url or load_config().get("api_url") or resolve_api_url()
    return AFRClient(api_url)


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
