"""Resume handlers — the client half of the AFR replay contract.

Register a function that knows how to resume *your* agent from a state dict:

    import afr

    @afr.register_resume_handler
    def resume(ctx: afr.ReplayContext):
        agent = MyAgent.from_state(ctx.state)
        return agent.continue_run()

Then `afr.replay(run_id, checkpoint_id)` (or `afr replay` from the CLI)
fetches the replay ticket from the backend and invokes your handler with a
ReplayContext. In `dry_run` mode the handler is *not* invoked — you just get
the ticket back.
"""

from __future__ import annotations

import concurrent.futures
import importlib
import os
from dataclasses import dataclass, field
from typing import Any, Callable

from afr.client import AFRClient
from afr.context import current_run
from afr.types import (
    EVENT_REPLAY_DISABLED,
    EVENT_REPLAY_FAILED,
    EVENT_REPLAY_LIMIT_EXHAUSTED,
    MODE_DRY_RUN,
)

ResumeHandler = Callable[["ReplayContext"], Any]

_handlers: dict[str, ResumeHandler] = {}


class ToolBlockedError(RuntimeError):
    """Raised by ReplayContext.call_tool for tools the replay plan blocks."""

    def __init__(self, tool: str, mode: str):
        self.tool = tool
        self.mode = mode
        super().__init__(
            f"tool {tool!r} is blocked under replay mode {mode!r} — it requires "
            "approval; re-request the replay with approved=true to allow it"
        )


class ReplayLimitExhausted(RuntimeError):
    """Raised when a replay exceeds operator-configured bounds."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"replay limit exhausted: {reason}")


def _replay_enabled() -> bool:
    """Read the runtime kill-switch (default off)."""
    return os.environ.get("AFR_REPLAY_ENABLED", "").lower() in ("1", "true", "yes")


def _replay_timeout_seconds() -> float | None:
    raw = os.environ.get("AFR_REPLAY_TIMEOUT_SECONDS")
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _replay_max_steps() -> int | None:
    raw = os.environ.get("AFR_REPLAY_MAX_STEPS")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _log_replay_event(
    client: AFRClient | None,
    run_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Emit a replay-lifecycle event to the active run or directly to the backend."""
    run = current_run()
    if run is not None:
        return run.log_event(event_type, name=event_type, payload=payload)
    if client is not None:
        return client.append_event(run_id, event_type, name=event_type, payload=payload)
    return {"event_id": None}


@dataclass
class ReplayContext:
    """Everything a resume handler needs to pick up where the run left off.

    Premium backends attach a per-tool safety plan (tool_plan) and recorded
    results for mocked tools (mock_results); the helpers below stay safe when
    talking to a free backend by treating unknown tools as mocked.
    """

    run_id: str
    checkpoint_id: str
    label: str | None
    mode: str
    state: dict[str, Any]
    ticket: dict[str, Any] = field(default_factory=dict)
    tool_plan: dict[str, dict[str, str]] = field(default_factory=dict)
    mock_results: dict[str, Any] = field(default_factory=dict)
    steps: int = field(default=0, init=False, repr=False)

    def action_for(self, tool: str) -> str:
        """'allow' | 'mock' | 'skip' | 'block' for a tool under this replay."""
        entry = self.tool_plan.get(tool)
        if entry and "action" in entry:
            return entry["action"]
        # no plan (free backend / unrecorded tool): never execute by accident
        return "skip" if self.mode == "dry_run" else "mock"

    def should_execute(self, tool: str) -> bool:
        return self.action_for(tool) == "allow"

    def mock_result(self, tool: str, default: Any = None) -> Any:
        """Last recorded successful result for a mocked tool, if any."""
        return self.mock_results.get(tool, default)

    def call_tool(
        self, tool: str, fn: Callable[..., Any], *args: Any, default: Any = None, **kwargs: Any
    ) -> Any:
        """Run a tool the way the replay plan says to.

        The server never executes your code — it only computes the plan. This
        helper is how a resume handler honors it without hand-rolling the
        action matrix:

            allow  -> fn(*args, **kwargs) really executes
            mock   -> last recorded result (or `default` if none was recorded)
            skip   -> `default`, nothing executes
            block  -> raises ToolBlockedError
        """
        self.steps += 1
        max_steps = _replay_max_steps()
        if max_steps is not None and self.steps > max_steps:
            raise ReplayLimitExhausted("max_steps")

        action = self.action_for(tool)
        if action == "allow":
            return fn(*args, **kwargs)
        if action == "mock":
            return self.mock_result(tool, default)
        if action == "skip":
            return default
        raise ToolBlockedError(tool, self.mode)


def register_resume_handler(
    fn: ResumeHandler | None = None, *, name: str = "default"
) -> Any:
    """Register a resume handler (usable bare or as @register_resume_handler)."""

    def _register(handler: ResumeHandler) -> ResumeHandler:
        _handlers[name] = handler
        return handler

    return _register(fn) if fn is not None else _register


def get_resume_handler(name: str = "default") -> ResumeHandler | None:
    return _handlers.get(name)


def clear_resume_handlers() -> None:
    _handlers.clear()


def load_callable(spec: str) -> Callable[..., Any]:
    """Load 'package.module:attr' — used by `afr replay --handler`."""
    module_name, _, attr = spec.partition(":")
    if not module_name or not attr:
        raise ValueError(f"handler spec must look like 'package.module:function', got {spec!r}")
    module = importlib.import_module(module_name)
    fn = getattr(module, attr)
    if not callable(fn):
        raise TypeError(f"{spec} is not callable")
    return fn


def build_replay_context(ticket: dict[str, Any]) -> ReplayContext:
    return ReplayContext(
        run_id=ticket["run_id"],
        checkpoint_id=ticket["checkpoint_id"],
        label=ticket.get("label"),
        mode=ticket.get("mode", MODE_DRY_RUN),
        state=ticket.get("state") or {},
        ticket=ticket,
        tool_plan=ticket.get("tool_plan") or {},
        mock_results=ticket.get("mock_results") or {},
    )


def _invoke_handler(handler: ResumeHandler, ctx: ReplayContext) -> Any:
    """Invoke a resume handler, applying operator bounds."""
    timeout = _replay_timeout_seconds()
    if timeout is None:
        return handler(ctx)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(handler, ctx)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError as exc:
            raise ReplayLimitExhausted("timeout") from exc


def replay(
    run_id: str,
    checkpoint_id: str,
    mode: str = MODE_DRY_RUN,
    *,
    client: AFRClient | None = None,
    api_url: str | None = None,
    handler: ResumeHandler | str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Request a replay ticket; invoke a resume handler unless mode is dry_run.

    Returns {"ticket": <server response>, "handler_result": <whatever your
    handler returned, or None>, "handler_invoked": bool}.
    """
    owns_client = client is None
    client = client or AFRClient(api_url)

    if not _replay_enabled():
        event = _log_replay_event(
            client,
            run_id,
            EVENT_REPLAY_DISABLED,
            {"actor": "replay", "reason": "replay disabled by operator"},
        )
        if owns_client:
            client.close()
        return {
            "disabled": True,
            "reason": "replay disabled by operator",
            "handler_invoked": False,
            "event_id": event.get("id") or event.get("event_id"),
        }

    try:
        ticket = client.replay(run_id, checkpoint_id, mode=mode, **extra)

        resolved: ResumeHandler | None
        if isinstance(handler, str):
            resolved = load_callable(handler)  # type: ignore[assignment]
        else:
            resolved = handler or get_resume_handler()

        result: Any = None
        invoked = False
        if mode != MODE_DRY_RUN and resolved is not None:
            ctx = build_replay_context(ticket)
            try:
                result = _invoke_handler(resolved, ctx)
            except ReplayLimitExhausted as exc:
                _log_replay_event(
                    client,
                    run_id,
                    EVENT_REPLAY_LIMIT_EXHAUSTED,
                    {"actor": "replay", "reason": exc.reason},
                )
                raise
            except Exception as exc:
                _log_replay_event(
                    client,
                    run_id,
                    EVENT_REPLAY_FAILED,
                    {
                        "actor": "replay",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    },
                )
                raise
            invoked = True

        return {"ticket": ticket, "handler_result": result, "handler_invoked": invoked}
    finally:
        if owns_client:
            client.close()
