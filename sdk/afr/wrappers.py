"""Decorators that record model/tool calls automatically.

    @afr.record_tool_call
    def search_web(query: str) -> list[str]: ...

    @afr.record_model_call(model="gpt-x", provider="openai")
    def ask_llm(prompt: str) -> str: ...

If there is no active run, the wrapped function runs untouched — decorate
freely, record only when a run is open. Exceptions are recorded (as a failed
call plus an `error` event) and re-raised.
"""

from __future__ import annotations

import functools
import time
import traceback
from typing import Any, Callable

from afr.context import current_run
from afr.types import jsonable


def _capture_args(args: tuple, kwargs: dict) -> dict[str, Any]:
    captured: dict[str, Any] = {}
    if args:
        captured["args"] = jsonable(list(args))
    if kwargs:
        captured["kwargs"] = jsonable(kwargs)
    return captured


def record_model_call(
    fn: Callable | None = None,
    *,
    model: str | None = None,
    provider: str | None = None,
    name: str | None = None,
    capture_args: bool = True,
    capture_result: bool = True,
) -> Callable:
    """Wrap a function whose call should be recorded as a `model_call` event."""

    def _decorate(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            run = current_run()
            if run is None:
                return func(*args, **kwargs)
            started = time.perf_counter()
            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                duration_ms = (time.perf_counter() - started) * 1000
                run.log_model(
                    model=model,
                    provider=provider,
                    name=name or func.__name__,
                    input=_capture_args(args, kwargs) if capture_args else None,
                    status="error",
                    error=f"{type(exc).__name__}: {exc}",
                    duration_ms=round(duration_ms, 2),
                    actor="wrapper",
                )
                run.log_error(
                    f"model call {func.__name__} failed: {exc}",
                    traceback=traceback.format_exc(),
                    actor="wrapper",
                )
                raise
            duration_ms = (time.perf_counter() - started) * 1000
            run.log_model(
                model=model,
                provider=provider,
                name=name or func.__name__,
                input=_capture_args(args, kwargs) if capture_args else None,
                output=jsonable(result) if capture_result else None,
                status="ok",
                duration_ms=round(duration_ms, 2),
                actor="wrapper",
            )
            return result

        return wrapper

    return _decorate(fn) if fn is not None else _decorate


def record_tool_call(
    fn: Callable | None = None,
    *,
    name: str | None = None,
    policy: str | None = None,
    capture_args: bool = True,
    capture_result: bool = True,
    **payload_extra: Any,
) -> Callable:
    """Wrap a function whose call should be recorded as a `tool_call` event.

    `policy` declares the tool's replay-safety class ("safe",
    "side_effecting", "mock_by_default", "requires_approval") and is stored
    on every recorded payload; the advanced replay engine enforces it.
    Unlabelled tools are treated as side_effecting. Extra keyword arguments
    are stored on the payload as-is.
    """

    def _decorate(func: Callable) -> Callable:
        tool_name = name or func.__name__
        if policy is not None:
            payload_extra["policy"] = policy

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            run = current_run()
            if run is None:
                return func(*args, **kwargs)
            started = time.perf_counter()
            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                duration_ms = (time.perf_counter() - started) * 1000
                run.log_tool(
                    tool_name,
                    args=_capture_args(args, kwargs) if capture_args else None,
                    status="error",
                    error=f"{type(exc).__name__}: {exc}",
                    duration_ms=round(duration_ms, 2),
                    actor="wrapper",
                    **payload_extra,
                )
                run.log_error(
                    f"tool {tool_name} failed: {exc}",
                    traceback=traceback.format_exc(),
                    actor="wrapper",
                )
                raise
            duration_ms = (time.perf_counter() - started) * 1000
            run.log_tool(
                tool_name,
                args=_capture_args(args, kwargs) if capture_args else None,
                result=jsonable(result) if capture_result else None,
                status="ok",
                duration_ms=round(duration_ms, 2),
                actor="wrapper",
                **payload_extra,
            )
            return result

        return wrapper

    return _decorate(fn) if fn is not None else _decorate
