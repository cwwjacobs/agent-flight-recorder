"""Replay safety policies (premium).

Tools carry a *policy* (recorded on their tool_call payloads, e.g. via
`@afr.record_tool_call(policy="safe")`); a replay request carries a *mode*.
The matrix below decides, per tool, what a resume handler is allowed to do.
Unknown tools default to `side_effecting` — the safe assumption.

                 │ safe   side_effecting  mock_by_default  requires_approval
  ───────────────┼────────────────────────────────────────────────────────
  dry_run        │ skip   skip            skip             skip
  mock_tools     │ mock   mock            mock             mock
  allow_safe     │ allow  mock            mock             mock
  allow_side_eff.│ allow  allow           mock             allow if approved
                 │                                         else block

Actions: allow = really execute · mock = use recorded result / fake ·
skip = plan only, nothing runs · block = refuse outright.

Modes `allow_safe_tools` and `allow_side_effects` require premium; `dry_run`
and `mock_tools` are free. The default mode is `dry_run` — by default nothing
executes, and no mode short of explicit `allow_side_effects` (+ approval for
gated tools) ever executes a side-effecting tool.
"""

from __future__ import annotations

from typing import Any

from app.storage import repo

POLICY_SAFE = "safe"
POLICY_SIDE_EFFECTING = "side_effecting"
POLICY_MOCK_BY_DEFAULT = "mock_by_default"
POLICY_REQUIRES_APPROVAL = "requires_approval"

POLICIES = (POLICY_SAFE, POLICY_SIDE_EFFECTING, POLICY_MOCK_BY_DEFAULT, POLICY_REQUIRES_APPROVAL)
DEFAULT_POLICY = POLICY_SIDE_EFFECTING

MODE_DRY_RUN = "dry_run"
MODE_MOCK_TOOLS = "mock_tools"
MODE_ALLOW_SAFE_TOOLS = "allow_safe_tools"
MODE_ALLOW_SIDE_EFFECTS = "allow_side_effects"

MODES = (MODE_DRY_RUN, MODE_MOCK_TOOLS, MODE_ALLOW_SAFE_TOOLS, MODE_ALLOW_SIDE_EFFECTS)
FREE_MODES = (MODE_DRY_RUN, MODE_MOCK_TOOLS)

ACTION_ALLOW = "allow"
ACTION_MOCK = "mock"
ACTION_SKIP = "skip"
ACTION_BLOCK = "block"


def decide(policy: str, mode: str, approved: bool = False) -> str:
    if policy not in POLICIES:
        policy = DEFAULT_POLICY
    if mode == MODE_DRY_RUN:
        return ACTION_SKIP
    if mode == MODE_MOCK_TOOLS:
        return ACTION_MOCK
    if mode == MODE_ALLOW_SAFE_TOOLS:
        return ACTION_ALLOW if policy == POLICY_SAFE else ACTION_MOCK
    if mode == MODE_ALLOW_SIDE_EFFECTS:
        if policy == POLICY_MOCK_BY_DEFAULT:
            return ACTION_MOCK
        if policy == POLICY_REQUIRES_APPROVAL:
            return ACTION_ALLOW if approved else ACTION_BLOCK
        return ACTION_ALLOW
    raise ValueError(f"unknown replay mode: {mode!r}")


def build_tool_plan(
    run_id: str, mode: str, approved: bool = False
) -> tuple[dict[str, dict[str, str]], dict[str, Any]]:
    """Plan every tool seen in the run + recorded results for mocked tools.

    Returns (plan, mock_results):
      plan          {tool: {"policy": ..., "action": ...}}
      mock_results  {tool: <last successful recorded result>} for tools whose
                    action is "mock" — record/replay-style mocking for free.
    """
    tool_events = repo.list_events(run_id, event_type="tool_call", limit=1_000_000)

    policies: dict[str, str] = {}
    last_results: dict[str, Any] = {}
    for event in tool_events:
        payload = event.get("payload") or {}
        tool = str(payload.get("tool") or event.get("name") or "unknown_tool")
        recorded_policy = payload.get("policy")
        if recorded_policy in POLICIES:
            policies[tool] = recorded_policy
        else:
            policies.setdefault(tool, DEFAULT_POLICY)
        if payload.get("status", "ok") == "ok" and "result" in payload:
            last_results[tool] = payload["result"]

    plan = {
        tool: {"policy": policy, "action": decide(policy, mode, approved)}
        for tool, policy in sorted(policies.items())
    }
    mock_results = {
        tool: last_results[tool]
        for tool, entry in plan.items()
        if entry["action"] == ACTION_MOCK and tool in last_results
    }
    return plan, mock_results
