"""Counterfactual replay harness (Meta hackathon build, Step 2).

Forks a recorded run at a checkpoint and replays the four fixed arms —
bare, generic context, selected cards, oracle — each with exactly one
declared delta, through AFR's existing resume-handler path.

Pieces:
  - arm_handler.resume_arm: the one resume handler serving all arms.
  - run_arms: a thin driver that runs the four arms over one fork point.
  - materials/: where delta material files live (see its README).
"""

from __future__ import annotations

from examples.counterfactual_replay.arm_handler import resume_arm

__all__ = ["resume_arm"]
