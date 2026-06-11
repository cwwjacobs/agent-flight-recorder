# Toy agent example

A scripted "trip planner" agent that records a complete flight-recorder run —
model calls, tool calls (including one deliberate failure + retry), state
snapshots, and three checkpoints. Runs fully offline.

```bash
# 1. backend up (from repo root)
cd backend && python -m app &

# 2. record a run
python examples/toy_agent/toy_agent.py

# 3. inspect
afr runs list
afr events <run_id>

# 4. replay from the first checkpoint through the example resume handler
afr replay <run_id> --from <checkpoint_id> \
    --mode mock_tools \
    --handler examples.toy_agent.replay_handler:resume
```

`replay_handler.py` shows the resume-handler contract: a function that takes
an `afr.ReplayContext` (run id, checkpoint id, mode, reconstructed state) and
continues your agent however you see fit.
