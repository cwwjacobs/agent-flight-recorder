"""MCP tool registry: the conceptual AFR toolset an LLM client would get."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.engine import (
    checkpoints as ckpt_engine,
    events as event_engine,
    forks as fork_engine,
    runs as run_engine,
)
from app.replay import prepare_replay


@dataclass(frozen=True)
class MCPTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Any]


def _afr_list_runs(status: str | None = None, tag: str | None = None, limit: int = 20) -> list:
    return run_engine.list_runs(status=status, tag=tag, limit=limit)


def _afr_get_run(run_id: str) -> dict:
    return run_engine.get_run_detail(run_id)


def _afr_get_events(run_id: str, event_type: str | None = None, limit: int = 200) -> list:
    return event_engine.list_events(run_id, event_type=event_type, limit=limit)


def _afr_get_state_at_checkpoint(run_id: str, checkpoint_id: str) -> dict:
    return ckpt_engine.state_at_checkpoint(run_id, checkpoint_id)


def _afr_replay(
    run_id: str, checkpoint_id: str, mode: str = "dry_run", approved: bool = False
) -> dict:
    return prepare_replay(run_id, checkpoint_id, mode=mode, approved=approved).to_dict()


def _afr_fork_run(run_id: str, checkpoint_id: str, name: str | None = None) -> dict:
    return fork_engine.fork_run(run_id, checkpoint_id, name=name)


def _afr_tag_run(run_id: str, tags: list[str]) -> dict:
    return run_engine.update_run(run_id, tags=tags)


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required}


_RUN_ID = {"type": "string", "description": "AFR run id"}
_CKPT_ID = {"type": "string", "description": "AFR checkpoint id"}

TOOLS: dict[str, MCPTool] = {
    tool.name: tool
    for tool in (
        MCPTool(
            "afr_list_runs",
            "List recorded agent runs (most recent first), with event/checkpoint counts.",
            _schema(
                {
                    "status": {"type": "string", "enum": ["running", "completed", "failed"]},
                    "tag": {"type": "string"},
                    "limit": {"type": "integer", "default": 20},
                },
                [],
            ),
            _afr_list_runs,
        ),
        MCPTool(
            "afr_get_run",
            "Get one run: status, metadata, tags, notes, fork lineage.",
            _schema({"run_id": _RUN_ID}, ["run_id"]),
            _afr_get_run,
        ),
        MCPTool(
            "afr_get_events",
            "Get a run's event timeline in order (model calls, tool calls, state, errors).",
            _schema(
                {
                    "run_id": _RUN_ID,
                    "event_type": {
                        "type": "string",
                        "enum": [
                            "model_call",
                            "tool_call",
                            "state_snapshot",
                            "checkpoint",
                            "log",
                            "error",
                        ],
                    },
                    "limit": {"type": "integer", "default": 200},
                },
                ["run_id"],
            ),
            _afr_get_events,
        ),
        MCPTool(
            "afr_get_state_at_checkpoint",
            "Reconstructed agent state as of a checkpoint.",
            _schema({"run_id": _RUN_ID, "checkpoint_id": _CKPT_ID}, ["run_id", "checkpoint_id"]),
            _afr_get_state_at_checkpoint,
        ),
        MCPTool(
            "afr_replay",
            "Request a replay ticket from a checkpoint. Safe by default: in "
            "dry_run/mock_tools nothing executes; side-effecting tools are "
            "mocked unless mode=allow_side_effects (and approved for gated tools).",
            _schema(
                {
                    "run_id": _RUN_ID,
                    "checkpoint_id": _CKPT_ID,
                    "mode": {
                        "type": "string",
                        "enum": ["dry_run", "mock_tools", "allow_safe_tools", "allow_side_effects"],
                        "default": "dry_run",
                    },
                    "approved": {"type": "boolean", "default": False},
                },
                ["run_id", "checkpoint_id"],
            ),
            _afr_replay,
        ),
        MCPTool(
            "afr_fork_run",
            "Fork a new run from a checkpoint (parent/child lineage recorded).",
            _schema(
                {"run_id": _RUN_ID, "checkpoint_id": _CKPT_ID, "name": {"type": "string"}},
                ["run_id", "checkpoint_id"],
            ),
            _afr_fork_run,
        ),
        MCPTool(
            "afr_tag_run",
            "Replace a run's tag list.",
            _schema(
                {"run_id": _RUN_ID, "tags": {"type": "array", "items": {"type": "string"}}},
                ["run_id", "tags"],
            ),
            _afr_tag_run,
        ),
    )
}


def get_tool_definitions() -> list[dict[str, Any]]:
    return [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in TOOLS.values()
    ]


def call_tool(name: str, arguments: dict[str, Any] | None = None) -> Any:
    tool = TOOLS.get(name)
    if tool is None:
        raise KeyError(name)
    return tool.handler(**(arguments or {}))
