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

import hashlib
import importlib
import multiprocessing as mp
import os
import time
from dataclasses import dataclass, field, replace
from typing import Any, Callable

from afr.client import AFRClient
from afr.context import current_run
from afr.types import (
    EVENT_REPLAY_DISABLED,
    EVENT_REPLAY_ACTION,
    EVENT_REPLAY_COMPLETED,
    EVENT_REPLAY_FAILED,
    EVENT_REPLAY_LIMIT_EXHAUSTED,
    EVENT_REPLAY_REJECTED,
    EVENT_REPLAY_STARTED,
    MODE_DRY_RUN,
)

ResumeHandler = Callable[["ReplayContext"], Any]
ReplayEventSink = Callable[[str, dict[str, Any]], dict[str, Any]]

DEFAULT_REPLAY_TIMEOUT_SECONDS = 30.0
DEFAULT_REPLAY_MAX_STEPS = 100

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


class ReplayHandlerProcessError(RuntimeError):
    """Raised when the isolated replay worker cannot return a handler outcome."""


def _replay_enabled() -> bool:
    """Read the runtime kill-switch (default off)."""
    return os.environ.get("AFR_REPLAY_ENABLED", "").lower() in ("1", "true", "yes")


def _replay_timeout_seconds() -> float:
    raw = os.environ.get("AFR_REPLAY_TIMEOUT_SECONDS")
    if raw is None or not raw.strip():
        return DEFAULT_REPLAY_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError as exc:
        raise ReplayLimitExhausted("invalid AFR_REPLAY_TIMEOUT_SECONDS") from exc
    if value <= 0:
        raise ReplayLimitExhausted("invalid AFR_REPLAY_TIMEOUT_SECONDS")
    return value


def _replay_max_steps() -> int:
    raw = os.environ.get("AFR_REPLAY_MAX_STEPS")
    if raw is None or not raw.strip():
        return DEFAULT_REPLAY_MAX_STEPS
    try:
        value = int(raw)
    except ValueError as exc:
        raise ReplayLimitExhausted("invalid AFR_REPLAY_MAX_STEPS") from exc
    if value <= 0:
        raise ReplayLimitExhausted("invalid AFR_REPLAY_MAX_STEPS")
    return value


def _value_digest(value: Any) -> str:
    """Return a content digest without writing the underlying value to audit logs."""
    return hashlib.sha256(repr(value).encode("utf-8", errors="replace")).hexdigest()


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
    correlation_id: str | None = None
    parent_event_id: str | None = None
    event_sink: ReplayEventSink | None = field(default=None, repr=False)
    steps: int = field(default=0, init=False, repr=False)

    def _record_action(
        self,
        *,
        tool: str,
        action: str,
        status: str,
        result: Any = None,
        error_type: str | None = None,
    ) -> None:
        if self.event_sink is None:
            return
        payload: dict[str, Any] = {
            "actor": "replay",
            "correlation_id": self.correlation_id,
            "parent_event_id": self.parent_event_id,
            "checkpoint_id": self.checkpoint_id,
            "mode": self.mode,
            "tool": tool,
            "action": action,
            "step": self.steps,
            "status": status,
        }
        if result is not None:
            payload["result_type"] = type(result).__name__
            payload["result_digest"] = _value_digest(result)
        if error_type is not None:
            payload["error_type"] = error_type
        self.event_sink(EVENT_REPLAY_ACTION, payload)

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
        if self.steps > max_steps:
            raise ReplayLimitExhausted("max_steps")

        action = self.action_for(tool)
        if action == "allow":
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:
                self._record_action(
                    tool=tool,
                    action=action,
                    status="failed",
                    error_type=type(exc).__name__,
                )
                raise
            self._record_action(tool=tool, action=action, status="completed", result=result)
            return result
        if action == "mock":
            result = self.mock_result(tool, default)
            self._record_action(tool=tool, action=action, status="mocked", result=result)
            return result
        if action == "skip":
            self._record_action(tool=tool, action=action, status="skipped")
            return default
        self._record_action(tool=tool, action=action, status="blocked")
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


def build_replay_context(
    ticket: dict[str, Any],
    *,
    correlation_id: str | None = None,
    parent_event_id: str | None = None,
    event_sink: ReplayEventSink | None = None,
) -> ReplayContext:
    return ReplayContext(
        run_id=ticket["run_id"],
        checkpoint_id=ticket["checkpoint_id"],
        label=ticket.get("label"),
        mode=ticket.get("mode", MODE_DRY_RUN),
        state=ticket.get("state") or {},
        ticket=ticket,
        tool_plan=ticket.get("tool_plan") or {},
        mock_results=ticket.get("mock_results") or {},
        correlation_id=correlation_id,
        parent_event_id=parent_event_id,
        event_sink=event_sink,
    )


def _handler_worker(handler: ResumeHandler, ctx: ReplayContext, send_conn: Any) -> None:
    """Run one handler inside an isolated worker process."""

    def _ipc_event_sink(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        send_conn.send(("event", event_type, payload))
        return {"event_id": None}

    ctx.event_sink = _ipc_event_sink
    try:
        result = handler(ctx)
        try:
            send_conn.send(("result", result, ctx.steps))
        except Exception as exc:
            send_conn.send(
                (
                    "transport_error",
                    f"handler result of type {type(result).__name__} could not cross "
                    f"the replay process boundary: {exc}",
                    ctx.steps,
                )
            )
    except BaseException as exc:
        try:
            send_conn.send(("error", exc, ctx.steps))
        except Exception:
            send_conn.send(
                (
                    "error_text",
                    f"{type(exc).__module__}.{type(exc).__qualname__}: {exc}",
                    ctx.steps,
                )
            )
    finally:
        send_conn.close()


def _replay_process_context() -> mp.context.BaseContext:
    # Prefer fork where available so locally defined handlers continue to work.
    # Platforms without fork use spawn; handlers there must be pickleable.
    methods = mp.get_all_start_methods()
    return mp.get_context("fork" if "fork" in methods else "spawn")


def _invoke_handler(handler: ResumeHandler, ctx: ReplayContext) -> Any:
    """Invoke a resume handler in a killable worker process."""
    timeout = _replay_timeout_seconds()
    process_ctx = _replay_process_context()
    recv_conn, send_conn = process_ctx.Pipe(duplex=False)
    child_ctx = replace(ctx, event_sink=None)
    process = process_ctx.Process(
        target=_handler_worker,
        args=(handler, child_ctx, send_conn),
        name="afr-replay-handler",
        daemon=True,
    )

    try:
        process.start()
    except Exception as exc:
        recv_conn.close()
        send_conn.close()
        raise ReplayHandlerProcessError(
            "replay handler could not start in an isolated process; on spawn-only "
            "platforms use an importable module-level handler"
        ) from exc
    finally:
        # The child owns its copy after process.start().
        send_conn.close()

    deadline = time.monotonic() + timeout
    terminal_message: tuple[Any, ...] | None = None

    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.terminate()
                process.join(timeout=1.0)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=1.0)
                raise ReplayLimitExhausted("timeout")

            if recv_conn.poll(min(0.05, remaining)):
                try:
                    message = recv_conn.recv()
                except EOFError:
                    message = None
                if message is not None and message[0] == "event":
                    if ctx.event_sink is not None:
                        ctx.event_sink(message[1], message[2])
                    continue
                terminal_message = message
                break

            if not process.is_alive():
                if recv_conn.poll():
                    continue
                break

        process.join(timeout=1.0)

        if terminal_message is None:
            raise ReplayHandlerProcessError(
                f"replay handler process exited without a result (exit code {process.exitcode})"
            )

        kind = terminal_message[0]
        if kind == "result":
            ctx.steps = int(terminal_message[2])
            return terminal_message[1]
        if kind == "error":
            ctx.steps = int(terminal_message[2])
            error = terminal_message[1]
            if isinstance(error, BaseException):
                raise error
            raise ReplayHandlerProcessError(str(error))
        if kind == "error_text":
            ctx.steps = int(terminal_message[2])
            raise ReplayHandlerProcessError(str(terminal_message[1]))
        if kind == "transport_error":
            ctx.steps = int(terminal_message[2])
            raise ReplayHandlerProcessError(str(terminal_message[1]))
        raise ReplayHandlerProcessError(f"unknown replay worker message: {kind!r}")
    finally:
        recv_conn.close()
        if process.is_alive():
            process.terminate()
            process.join(timeout=1.0)
            if process.is_alive():
                process.kill()
                process.join(timeout=1.0)


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
            {
                "actor": "replay",
                "checkpoint_id": checkpoint_id,
                "mode": mode,
                "reason": "replay disabled by operator",
            },
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

        ticket_is_mapping = isinstance(ticket, dict)
        raw_status = ticket.get("status") if ticket_is_mapping else None
        ticket_status = raw_status if isinstance(raw_status, str) else None
        parent_event_id = (
            ticket.get("replay_event_id") if ticket_is_mapping else None
        )
        correlation_id = parent_event_id

        # The server response is an authorization boundary. Only an exact
        # `ready` status may progress to handler resolution or invocation.
        if ticket_status != "ready":
            status_label = ticket_status or "missing_or_malformed"
            rejection = _log_replay_event(
                client,
                run_id,
                EVENT_REPLAY_REJECTED,
                {
                    "actor": "replay",
                    "correlation_id": correlation_id,
                    "parent_event_id": parent_event_id,
                    "checkpoint_id": checkpoint_id,
                    "mode": mode,
                    "ticket_status": status_label,
                    "reason": "replay ticket was not ready",
                    "server_response_type": type(ticket).__name__,
                },
            )
            return {
                "ticket": ticket if ticket_is_mapping else {},
                "handler_result": None,
                "handler_invoked": False,
                "rejected": True,
                "disabled": ticket_status == "disabled",
                "limit_exhausted": ticket_status == "limit_exhausted",
                "reason": f"replay ticket status is not ready: {status_label}",
                "event_id": rejection.get("id") or rejection.get("event_id"),
            }

        resolved: ResumeHandler | None
        if isinstance(handler, str):
            resolved = load_callable(handler)  # type: ignore[assignment]
        else:
            resolved = handler or get_resume_handler()

        result: Any = None
        invoked = False
        if mode != MODE_DRY_RUN and resolved is not None:
            start_event = _log_replay_event(
                client,
                run_id,
                EVENT_REPLAY_STARTED,
                {
                    "actor": "replay",
                    "correlation_id": correlation_id,
                    "parent_event_id": parent_event_id,
                    "checkpoint_id": checkpoint_id,
                    "mode": mode,
                    "status": "started",
                },
            )
            start_event_id = start_event.get("id") or start_event.get("event_id")
            correlation_id = correlation_id or start_event_id

            def _event_sink(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
                payload.setdefault("actor", "replay")
                payload.setdefault("correlation_id", correlation_id)
                payload.setdefault("parent_event_id", start_event_id)
                return _log_replay_event(client, run_id, event_type, payload)

            ctx = build_replay_context(
                ticket,
                correlation_id=correlation_id,
                parent_event_id=start_event_id,
                event_sink=_event_sink,
            )
            try:
                result = _invoke_handler(resolved, ctx)
            except ReplayLimitExhausted as exc:
                _log_replay_event(
                    client,
                    run_id,
                    EVENT_REPLAY_LIMIT_EXHAUSTED,
                    {
                        "actor": "replay",
                        "correlation_id": correlation_id,
                        "parent_event_id": start_event_id,
                        "checkpoint_id": checkpoint_id,
                        "mode": mode,
                        "reason": exc.reason,
                        "status": "limit_exhausted",
                    },
                )
                raise
            except Exception as exc:
                _log_replay_event(
                    client,
                    run_id,
                    EVENT_REPLAY_FAILED,
                    {
                        "actor": "replay",
                        "correlation_id": correlation_id,
                        "parent_event_id": start_event_id,
                        "checkpoint_id": checkpoint_id,
                        "mode": mode,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "status": "failed",
                    },
                )
                raise
            invoked = True
            _log_replay_event(
                client,
                run_id,
                EVENT_REPLAY_COMPLETED,
                {
                    "actor": "replay",
                    "correlation_id": correlation_id,
                    "parent_event_id": start_event_id,
                    "checkpoint_id": checkpoint_id,
                    "mode": mode,
                    "status": "completed",
                    "handler_result_type": type(result).__name__,
                    "handler_result_digest": _value_digest(result),
                    "steps": ctx.steps,
                },
            )

        return {"ticket": ticket, "handler_result": result, "handler_invoked": invoked}
    finally:
        if owns_client:
            client.close()
