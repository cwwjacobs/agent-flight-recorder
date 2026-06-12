"""LangChain-like demo: the adapter adoption story, zero API keys.

This is exactly how you'd attach AFR to a real LangChain/LangGraph app —
`config={"callbacks": [AFRCallbackHandler()]}` — except the "chain" here is
a 40-line fake that emits the same callback sequence LangChain does, so the
demo runs offline with nothing installed beyond the AFR SDK.

Usage:
    1. start the backend:  make serve   (or docker compose up --build)
    2. run this:           python examples/langchain_like_agent/agent.py
    3. inspect:            open http://127.0.0.1:8700
"""

from __future__ import annotations

import json
from uuid import uuid4

import afr
from afr.integrations.langchain import AFRCallbackHandler
from afr.types import resolve_api_url


class PaymentTimeout(Exception):
    pass


class FakeRefundChain:
    """Emits the same callback lifecycle a LangChain chain would."""

    def __init__(self, callbacks: list):
        self.callbacks = callbacks

    def _emit(self, method: str, *args, **kwargs) -> None:
        for cb in self.callbacks:
            getattr(cb, method)(*args, **kwargs)

    def invoke(self, inputs: dict) -> dict:
        chain_id = uuid4()
        self._emit("on_chain_start", {"name": "refund_chain"}, inputs, run_id=chain_id)
        try:
            llm_id = uuid4()
            self._emit(
                "on_llm_start", {"name": "fake-llm"}, [f"plan: {inputs['input']}"],
                run_id=llm_id, invocation_params={"model_name": "fake-llm-1"},
            )
            self._emit(
                "on_llm_end",
                _llm_result("1) look up the order 2) refund the customer"),
                run_id=llm_id,
            )

            lookup_id = uuid4()
            self._emit("on_tool_start", {"name": "lookup_order"}, "ord-20917", run_id=lookup_id)
            order = {"order_id": "ord-20917", "total_usd": 129.0, "status": "paid"}
            self._emit("on_tool_end", order, run_id=lookup_id)

            afr.log_state({"order": order, "step": "order_loaded"})
            afr.checkpoint("before-refund")  # ← the replayable moment

            refund_id = uuid4()
            self._emit("on_tool_start", {"name": "issue_refund"}, "ord-20917", run_id=refund_id)
            error = PaymentTimeout("refund provider did not respond within 30s")
            self._emit("on_tool_error", error, run_id=refund_id)
            raise error
        except PaymentTimeout as exc:
            self._emit("on_chain_error", exc, run_id=chain_id)
            raise
        # (unreachable in this demo) on success LangChain would emit:
        # self._emit("on_chain_end", outputs, run_id=chain_id)


def _llm_result(text: str):
    class Gen:
        def __init__(self, t): self.text = t

    class Result:
        generations = [[Gen(text)]]
        llm_output = {"token_usage": {"prompt_tokens": 21, "completion_tokens": 14, "total_tokens": 35}}

    return Result()


def main() -> None:
    handler = AFRCallbackHandler(
        require_langchain=False,  # fake chain; with real LangChain, drop this
        default_tool_policy="side_effecting",
        tool_policies={"lookup_order": "safe", "issue_refund": "requires_approval"},
    )
    chain = FakeRefundChain(callbacks=[handler])

    checkpoint_id = None
    try:
        with afr.start_run("langchain-demo", metadata={"adapter": "langchain", "example": True}) as run:
            run_id = run.run_id
            print(f"recording run {run_id}")
            chain.invoke({"input": "Refund order ord-20917"})
    except PaymentTimeout:
        print("chain failed with PaymentTimeout (on purpose) — run is marked failed")

    with afr.AFRClient() as client:
        checkpoint_id = client.list_checkpoints(run_id)[0]["id"]
        ticket = client.replay(run_id, checkpoint_id, mode="mock_tools")

    print()
    print("replay plan from checkpoint 'before-refund' (mock_tools):")
    for tool, entry in ticket["tool_plan"].items():
        print(f"  - {tool}: {entry['action']} (policy: {entry['policy']})")
    print()
    print("state at the checkpoint:")
    print(json.dumps(ticket["state"], indent=2))
    print()
    print(f"inspect the run:  {resolve_api_url()}/#/runs/{run_id}")
    print(f"or via CLI:       afr runs show {run_id[:8]}")


if __name__ == "__main__":
    main()
