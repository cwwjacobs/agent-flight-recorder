from __future__ import annotations

from afr_cli.main import build_parser


def test_parser_accepts_latest_shortcuts():
    parser = build_parser()

    args = parser.parse_args(["inspect", "latest", "--calls"])
    assert args.command == "inspect"
    assert args.run_id == "latest"
    assert args.calls is True

    args = parser.parse_args(["calls"])
    assert args.command == "calls"
    assert args.run_id == "latest"

    args = parser.parse_args(["repair-case", "latest", "--from", "latest", "-o", "cases/demo"])
    assert args.command == "repair-case"
    assert args.run_id == "latest"
    assert args.from_checkpoint == "latest"
    assert args.output == "cases/demo"


def test_parser_accepts_demo_and_aliases():
    parser = build_parser()

    args = parser.parse_args(["demo", "--seed"])
    assert args.command == "demo"
    assert args.seed is True

    args = parser.parse_args(["ls", "--status", "failed"])
    assert args.command == "ls"
    assert args.status == "failed"

    args = parser.parse_args(["show"])
    assert args.command == "show"
    assert args.run_id == "latest"
