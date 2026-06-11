"""Agent Flight Recorder SDK.

Quick start:

    import afr

    with afr.start_run("trip-planner", metadata={"env": "dev"}) as run:
        afr.log_model(model="gpt-x", input="plan a trip", output="...")
        afr.log_tool("search_flights", args={"to": "TYO"}, result={"price": 512})
        afr.log_state({"step": "flights_booked"})
        afr.checkpoint("after-flights")

Module-level helpers operate on the innermost active `with afr.start_run()`
block; everything is also available as methods on the RunContext it returns.
"""

from __future__ import annotations

from typing import Any

from afr.client import AFRAPIError, AFRClient
from afr.context import NoActiveRun, RunContext, current_run, require_run, start_run
from afr.hooks import (
    ReplayContext,
    build_replay_context,
    clear_resume_handlers,
    get_resume_handler,
    load_callable,
    register_resume_handler,
    replay,
)
from afr.types import EVENT_TYPES, REPLAY_MODES, jsonable
from afr.wrappers import record_model_call, record_tool_call

__version__ = "0.1.0"

__all__ = [
    "AFRClient",
    "AFRAPIError",
    "RunContext",
    "ReplayContext",
    "NoActiveRun",
    "start_run",
    "current_run",
    "require_run",
    "log_model",
    "log_tool",
    "log_state",
    "log_event",
    "log",
    "log_error",
    "checkpoint",
    "end_run",
    "record_model_call",
    "record_tool_call",
    "register_resume_handler",
    "get_resume_handler",
    "clear_resume_handlers",
    "build_replay_context",
    "load_callable",
    "replay",
    "jsonable",
    "EVENT_TYPES",
    "REPLAY_MODES",
]


# -- module-level conveniences over the current run --------------------------


def log_model(**kwargs: Any) -> dict:
    return require_run().log_model(**kwargs)


def log_tool(tool: str, **kwargs: Any) -> dict:
    return require_run().log_tool(tool, **kwargs)


def log_state(state: dict, mode: str = "replace", name: str | None = None) -> dict:
    return require_run().log_state(state, mode=mode, name=name)


def log_event(event_type: str, name: str | None = None, payload: dict | None = None) -> dict:
    return require_run().log_event(event_type, name=name, payload=payload)


def log(message: str, level: str = "info", **data: Any) -> dict:
    return require_run().log(message, level=level, **data)


def log_error(message: str, **kwargs: Any) -> dict:
    return require_run().log_error(message, **kwargs)


def checkpoint(label: str | None = None, state: dict | None = None) -> dict:
    return require_run().checkpoint(label=label, state=state)


def end_run(status: str = "completed") -> dict:
    return require_run().end(status=status)
