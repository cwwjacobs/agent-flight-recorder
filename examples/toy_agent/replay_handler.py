"""Example resume handler — the client half of the AFR replay contract.

Invoke via the CLI (from the repo root so the module path resolves):

    afr replay <run_id> --from <checkpoint_id> \
        --mode mock_tools \
        --handler examples.toy_agent.replay_handler:resume

or programmatically:

    import afr
    from examples.toy_agent.replay_handler import resume

    afr.replay(run_id, checkpoint_id, mode="mock_tools", handler=resume)
"""

from __future__ import annotations

import json

import afr


def resume(ctx: afr.ReplayContext) -> dict:
    """Resume the toy trip planner from a checkpoint's reconstructed state."""
    print(f"[resume] run        : {ctx.run_id}")
    print(f"[resume] checkpoint : {ctx.checkpoint_id} ({ctx.label})")
    print(f"[resume] mode       : {ctx.mode}")
    print("[resume] state:")
    print(json.dumps(ctx.state, indent=2))

    booked = ctx.state.get("booked", {})
    remaining = [step for step in ("flight", "hotel", "itinerary") if step not in booked
                 and step not in ctx.state]

    print(f"[resume] already done: {sorted(booked)}")
    print(f"[resume] would continue with: {remaining or 'nothing — run was complete'}")

    # ctx.call_tool honors the server's replay plan, so this handler never
    # re-executes a side-effecting tool by accident: under mock_tools the
    # recorded result (or the default) comes back without running anything.
    if "hotel" in remaining:
        from examples.toy_agent.toy_agent import search_hotels

        hotel = ctx.call_tool(
            "search_hotels", search_hotels, "Tokyo", nights=3,
            default={"hotel": "Hotel Mocked", "nights": 3},
        )
        print(f"[resume] search_hotels -> {ctx.action_for('search_hotels')}: {hotel}")

    # A real handler would rebuild your agent from ctx.state and keep going,
    # typically recording into a fresh run (or a Premium fork of this one).
    return {"resumed_from": ctx.label, "remaining_steps": remaining}
