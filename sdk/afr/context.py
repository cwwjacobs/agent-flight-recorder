"""Run context: the ergonomic layer of the SDK.

    import afr

    with afr.start_run("my-agent") as run:
        run.log_model(model="gpt-x", input=prompt, output=answer)
        run.log_tool("search", args={"q": "..."}, result=hits)
        run.log_state({"step": 1})
        run.checkpoint("after-search")

The active run is tracked in a contextvar, so module-level helpers
(afr.log_model, afr.checkpoint, ...) and the decorators in wrappers.py find
it without explicit plumbing — including across threads spawned with
contextvars propagation and async tasks.
"""

from __future__ import annotations

import traceback as tb_module
from contextvars import ContextVar
from typing import Any

from afr.client import AFRClient
from afr.types import (
    EVENT_CHECKPOINT,
    EVENT_ERROR,
    EVENT_LOG,
    EVENT_MODEL_CALL,
    EVENT_STATE_SNAPSHOT,
    EVENT_TOOL_CALL,
    jsonable,
)

_current_run: ContextVar["RunContext | None"] = ContextVar("afr_current_run", default=None)


class NoActiveRun(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "No active AFR run. Use `with afr.start_run(...):` or pass a RunContext explicitly."
        )


class RunContext:
    """Handle for one recorded run. Create via afr.start_run()."""

    def __init__(self, client: AFRClient, run: dict, *, owns_client: bool = False):
        self.client = client
        self.run = run
        self._owns_client = owns_client
        self._cv_token = None

    # -- identity -----------------------------------------------------------

    @property
    def run_id(self) -> str:
        return self.run["id"]

    @property
    def name(self) -> str:
        return self.run["name"]

    # -- logging ------------------------------------------------------------

    def log_event(
        self, event_type: str, name: str | None = None, payload: dict | None = None
    ) -> dict:
        return self.client.append_event(
            self.run_id, event_type, name=name, payload=jsonable(payload or {})
        )

    def log_model(
        self,
        *,
        model: str | None = None,
        provider: str | None = None,
        input: Any = None,
        output: Any = None,
        status: str = "ok",
        error: str | None = None,
        duration_ms: float | None = None,
        name: str | None = None,
        **extra: Any,
    ) -> dict:
        payload = {
            "model": model,
            "provider": provider,
            "input": input,
            "output": output,
            "status": status,
            "error": error,
            "duration_ms": duration_ms,
            **extra,
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        payload.setdefault("status", status)
        return self.log_event(EVENT_MODEL_CALL, name=name or model or "model_call", payload=payload)

    def log_tool(
        self,
        tool: str,
        *,
        args: Any = None,
        result: Any = None,
        status: str = "ok",
        error: str | None = None,
        duration_ms: float | None = None,
        **extra: Any,
    ) -> dict:
        payload = {
            "tool": tool,
            "args": args,
            "result": result,
            "status": status,
            "error": error,
            "duration_ms": duration_ms,
            **extra,
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        payload.setdefault("status", status)
        return self.log_event(EVENT_TOOL_CALL, name=tool, payload=payload)

    def log_state(self, state: dict, mode: str = "replace", name: str | None = None) -> dict:
        return self.log_event(
            EVENT_STATE_SNAPSHOT, name=name or "state", payload={"state": state, "mode": mode}
        )

    def log(self, message: str, level: str = "info", **data: Any) -> dict:
        payload: dict[str, Any] = {"level": level, "message": message}
        if data:
            payload["data"] = data
        return self.log_event(EVENT_LOG, name=level, payload=payload)

    def log_error(self, message: str, *, traceback: str | None = None, **data: Any) -> dict:
        payload: dict[str, Any] = {"message": message}
        if traceback:
            payload["traceback"] = traceback
        if data:
            payload["data"] = data
        return self.log_event(EVENT_ERROR, name="error", payload=payload)

    # -- checkpoints ----------------------------------------------------------

    def checkpoint(self, label: str | None = None, state: dict | None = None) -> dict:
        return self.client.checkpoint(
            self.run_id, label=label, state=jsonable(state) if state is not None else None
        )

    # -- lifecycle ------------------------------------------------------------

    def end(self, status: str = "completed") -> dict:
        self.run = self.client.end_run(self.run_id, status=status)
        return self.run

    def __enter__(self) -> "RunContext":
        self._cv_token = _current_run.set(self)
        return self

    def __exit__(self, exc_type: Any, exc: Any, _tb: Any) -> None:
        try:
            if exc_type is not None:
                self.log_error(
                    f"{exc_type.__name__}: {exc}",
                    traceback="".join(tb_module.format_exception(exc_type, exc, _tb)),
                )
                self.end(status="failed")
            else:
                self.end(status="completed")
        finally:
            if self._cv_token is not None:
                _current_run.reset(self._cv_token)
                self._cv_token = None
            if self._owns_client:
                self.client.close()


def start_run(
    name: str | None = None,
    metadata: dict | None = None,
    *,
    client: AFRClient | None = None,
    api_url: str | None = None,
) -> RunContext:
    """Create a run and return its context (usable as a context manager)."""
    owns_client = client is None
    client = client or AFRClient(api_url)
    run = client.create_run(name=name, metadata=jsonable(metadata or {}))
    return RunContext(client, run, owns_client=owns_client)


def current_run() -> RunContext | None:
    return _current_run.get()


def require_run(run: RunContext | None = None) -> RunContext:
    ctx = run or current_run()
    if ctx is None:
        raise NoActiveRun()
    return ctx
