"""LangChain / LangGraph adapter: one callback handler, one-line adoption.

    import afr
    from afr.integrations.langchain import AFRCallbackHandler

    handler = AFRCallbackHandler(default_tool_policy="side_effecting")

    with afr.start_run("langchain-demo"):
        chain.invoke({"input": "..."}, config={"callbacks": [handler]})
        afr.checkpoint("after-chain")

Mapping:

    on_llm_* / on_chat_model_start   -> model_call events
    on_tool_*                        -> tool_call events (with replay policy)
    on_chain_error / on_llm_error    -> error events
    on_chain_start/end               -> log events (+ optional checkpoint)

The module imports cleanly without LangChain installed (so the rest of the
SDK never pays for it); *constructing* the handler requires `langchain-core`
unless you pass `require_langchain=False`, which is intended for tests and
LangChain-like frameworks that duck-type the same callback methods.

Callback signatures vary across LangChain versions, so every method is
defensive: positional payloads are inspected with getattr/dict fallbacks and
unknown keyword arguments are ignored.
"""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from afr.context import RunContext, current_run, start_run
from afr.types import jsonable

try:  # optional dependency — see module docstring
    from langchain_core.callbacks.base import BaseCallbackHandler as _BaseHandler

    HAS_LANGCHAIN = True
except ImportError:
    _BaseHandler = object  # type: ignore[assignment,misc]
    HAS_LANGCHAIN = False

INSTALL_HINT = (
    "LangChain is not installed. Install the optional extra with:\n"
    "    pip install 'afr-sdk[langchain]'\n"
    "(or `pip install langchain-core` directly). To use this handler with a "
    "LangChain-like framework or in tests without LangChain, pass "
    "AFRCallbackHandler(require_langchain=False)."
)


def _name_from(serialized: Any, default: str) -> str:
    if isinstance(serialized, dict):
        if serialized.get("name"):
            return str(serialized["name"])
        ident = serialized.get("id")
        if isinstance(ident, (list, tuple)) and ident:
            return str(ident[-1])
    return default


def _model_from(serialized: Any, kwargs: dict) -> str | None:
    params = kwargs.get("invocation_params") or {}
    for source in (params, serialized if isinstance(serialized, dict) else {}):
        for key in ("model", "model_name", "model_id"):
            if source.get(key):
                return str(source[key])
    return None


def _llm_output_text(response: Any) -> Any:
    """Best-effort text from an LLMResult-shaped object."""
    generations = getattr(response, "generations", None)
    if generations is None and isinstance(response, dict):
        generations = response.get("generations")
    texts: list[str] = []
    for batch in generations or []:
        for gen in batch if isinstance(batch, (list, tuple)) else [batch]:
            text = getattr(gen, "text", None)
            if text is None and isinstance(gen, dict):
                text = gen.get("text")
            if text:
                texts.append(str(text))
    if texts:
        return texts if len(texts) > 1 else texts[0]
    return None


def _token_usage(response: Any) -> dict | None:
    llm_output = getattr(response, "llm_output", None)
    if llm_output is None and isinstance(response, dict):
        llm_output = response.get("llm_output")
    if isinstance(llm_output, dict):
        usage = llm_output.get("token_usage") or llm_output.get("usage")
        if isinstance(usage, dict):
            return usage
    return None


class AFRCallbackHandler(_BaseHandler):  # type: ignore[valid-type,misc]
    """Records LangChain/LangGraph callback traffic into the active AFR run.

    Args:
        run_name: if no `with afr.start_run(...)` is active when the first
            callback fires, a run with this name is started automatically and
            ended when the outermost chain finishes. Inside an existing run
            context this is ignored.
        capture_prompts: record prompts/messages/tool inputs (default True).
        capture_outputs: record completions/tool outputs (default True).
        default_tool_policy: replay policy stamped on recorded tool calls
            ("safe", "side_effecting", "mock_by_default", "requires_approval");
            per-tool overrides via `tool_policies={"charge": "requires_approval"}`.
        checkpoint_on_chain_end: create a checkpoint when the outermost chain
            ends (default False).
        require_langchain: set False to use the handler without langchain-core
            installed (fake/duck-typed callback sources, tests).
    """

    # tell LangChain not to swallow our errors silently
    raise_error = False

    def __init__(
        self,
        *,
        run_name: str | None = None,
        capture_prompts: bool = True,
        capture_outputs: bool = True,
        default_tool_policy: str = "side_effecting",
        tool_policies: dict[str, str] | None = None,
        checkpoint_on_chain_end: bool = False,
        require_langchain: bool = True,
    ):
        if require_langchain and not HAS_LANGCHAIN:
            raise ImportError(INSTALL_HINT)
        self.run_name = run_name
        self.capture_prompts = capture_prompts
        self.capture_outputs = capture_outputs
        self.default_tool_policy = default_tool_policy
        self.tool_policies = tool_policies or {}
        self.checkpoint_on_chain_end = checkpoint_on_chain_end
        self._owned_run: RunContext | None = None
        self._chain_depth = 0
        self._starts: dict[Any, dict[str, Any]] = {}

    # -- run plumbing ---------------------------------------------------------

    def _run(self) -> RunContext | None:
        active = current_run()
        if active is not None:
            return active
        if self._owned_run is not None:
            return self._owned_run
        if self.run_name:
            self._owned_run = start_run(self.run_name, metadata={"adapter": "langchain"})
            return self._owned_run
        return None

    def _end_owned_run(self, status: str) -> None:
        if self._owned_run is not None and self._chain_depth <= 0:
            self._owned_run.end(status=status)
            self._owned_run = None

    def _remember_start(self, run_id: Any, **info: Any) -> None:
        if run_id is not None:
            self._starts[run_id] = {"started": time.perf_counter(), **info}

    def _take_start(self, run_id: Any) -> dict[str, Any]:
        info = self._starts.pop(run_id, None)
        if info is None:
            return {}
        info["duration_ms"] = round((time.perf_counter() - info.pop("started")) * 1000, 2)
        return info

    # -- LLMs -------------------------------------------------------------------

    def on_llm_start(
        self, serialized: Any = None, prompts: Any = None, *, run_id: UUID | None = None, **kwargs: Any
    ) -> None:
        self._remember_start(
            run_id,
            name=_name_from(serialized, "llm"),
            model=_model_from(serialized, kwargs),
            prompts=jsonable(prompts) if self.capture_prompts else None,
        )

    def on_chat_model_start(
        self, serialized: Any = None, messages: Any = None, *, run_id: UUID | None = None, **kwargs: Any
    ) -> None:
        self._remember_start(
            run_id,
            name=_name_from(serialized, "chat_model"),
            model=_model_from(serialized, kwargs),
            prompts=jsonable(messages) if self.capture_prompts else None,
        )

    def on_llm_end(self, response: Any = None, *, run_id: UUID | None = None, **kwargs: Any) -> None:
        run = self._run()
        if run is None:
            return
        info = self._take_start(run_id)
        run.log_model(
            name=info.get("name") or "llm",
            model=info.get("model"),
            provider="langchain",
            input=info.get("prompts"),
            output=_llm_output_text(response) if self.capture_outputs else None,
            status="ok",
            duration_ms=info.get("duration_ms"),
            **({"usage": _token_usage(response)} if _token_usage(response) else {}),
        )

    def on_llm_error(self, error: BaseException, *, run_id: UUID | None = None, **kwargs: Any) -> None:
        run = self._run()
        if run is None:
            return
        info = self._take_start(run_id)
        run.log_model(
            name=info.get("name") or "llm",
            model=info.get("model"),
            provider="langchain",
            input=info.get("prompts"),
            status="error",
            error=f"{type(error).__name__}: {error}",
            duration_ms=info.get("duration_ms"),
        )
        run.log_error(f"model call failed: {error}")

    # -- tools --------------------------------------------------------------------

    def _policy_for(self, tool: str) -> str:
        return self.tool_policies.get(tool, self.default_tool_policy)

    def on_tool_start(
        self, serialized: Any = None, input_str: Any = None, *, run_id: UUID | None = None, **kwargs: Any
    ) -> None:
        self._remember_start(
            run_id,
            tool=_name_from(serialized, "tool"),
            args=jsonable(kwargs.get("inputs", input_str)) if self.capture_prompts else None,
        )

    def on_tool_end(self, output: Any = None, *, run_id: UUID | None = None, **kwargs: Any) -> None:
        run = self._run()
        if run is None:
            return
        info = self._take_start(run_id)
        tool = info.get("tool") or kwargs.get("name") or "tool"
        run.log_tool(
            tool,
            args=info.get("args"),
            result=jsonable(output) if self.capture_outputs else None,
            status="ok",
            duration_ms=info.get("duration_ms"),
            policy=self._policy_for(tool),
        )

    def on_tool_error(self, error: BaseException, *, run_id: UUID | None = None, **kwargs: Any) -> None:
        run = self._run()
        if run is None:
            return
        info = self._take_start(run_id)
        tool = info.get("tool") or kwargs.get("name") or "tool"
        run.log_tool(
            tool,
            args=info.get("args"),
            status="error",
            error=f"{type(error).__name__}: {error}",
            duration_ms=info.get("duration_ms"),
            policy=self._policy_for(tool),
        )
        run.log_error(f"tool {tool} failed: {error}")

    # -- chains / agents -------------------------------------------------------------

    def on_chain_start(
        self, serialized: Any = None, inputs: Any = None, *, run_id: UUID | None = None, **kwargs: Any
    ) -> None:
        self._chain_depth += 1
        run = self._run()  # starts the owned run lazily if configured
        if run is not None and self._chain_depth == 1:
            run.log(
                f"chain {_name_from(serialized, 'chain')} started",
                inputs=jsonable(inputs) if self.capture_prompts else None,
            )

    def on_chain_end(self, outputs: Any = None, *, run_id: UUID | None = None, **kwargs: Any) -> None:
        self._chain_depth = max(0, self._chain_depth - 1)
        run = self._run()
        if run is None:
            return
        if self._chain_depth == 0:
            run.log(
                "chain finished",
                outputs=jsonable(outputs) if self.capture_outputs else None,
            )
            if self.checkpoint_on_chain_end:
                run.checkpoint("chain-end")
        self._end_owned_run("completed")

    def on_chain_error(self, error: BaseException, *, run_id: UUID | None = None, **kwargs: Any) -> None:
        self._chain_depth = max(0, self._chain_depth - 1)
        run = self._run()
        if run is None:
            return
        run.log_error(f"chain failed: {type(error).__name__}: {error}")
        self._end_owned_run("failed")

    # -- agent hooks (no-ops kept explicit so subclasses see the surface) ---------

    def on_agent_action(self, action: Any = None, **kwargs: Any) -> None:
        pass

    def on_agent_finish(self, finish: Any = None, **kwargs: Any) -> None:
        pass
