"""The AFR replay contract.

Replay is deliberately split between server and client:

  SERVER (this backend)
    - validates the run + checkpoint
    - reconstructs the state as of that checkpoint
    - records a `log` event ("replay_requested") on the run's timeline
    - returns a *replay ticket* — a plain JSON document

  CLIENT (the AFR SDK in the user's process)
    - receives the ticket
    - looks up the resume handler the user registered via
      `afr.hooks.register_resume_handler`
    - calls it with a ReplayContext: run_id, checkpoint_id, label, mode,
      and the reconstructed state

The server never executes user code. The ticket is the entire interface, so
anything that can read JSON can implement a resume handler (Python SDK, CLI
`--handler module:fn`, or your own runtime).

MVP modes:
    dry_run  — return the ticket only; SDK does not invoke any handler
    (other)  — passed through to the handler untouched

Premium replaces the free-form mode with a validated safety-policy engine
(dry_run / mock_tools / allow_safe_tools / allow_side_effects).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ReplayTicket:
    run_id: str
    checkpoint_id: str
    label: str | None
    mode: str
    state: dict[str, Any]
    status: str
    message: str
    replay_event_id: str
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        extras = d.pop("extras", {})
        d.update(extras)
        return d
