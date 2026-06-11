import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Checkpoint, StateAt } from "../api/types";
import { JsonTree } from "./JsonTree";
import { fmtClock, shortId } from "../util/format";

export function StatePanel({
  runId,
  checkpoints,
  selectedId,
  onSelect,
}: {
  runId: string;
  checkpoints: Checkpoint[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const [stateAt, setStateAt] = useState<StateAt | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!selectedId) {
      setStateAt(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .getStateAt(runId, selectedId)
      .then((doc) => !cancelled && setStateAt(doc))
      .catch((e) => !cancelled && setError(String(e)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [runId, selectedId]);

  return (
    <section className="panel panel-ticks">
      <div className="panel-head">
        <span className="panel-title">State @ Checkpoint</span>
      </div>
      <div className="panel-body">
        {checkpoints.length === 0 ? (
          <div className="state-empty">no checkpoints in this run</div>
        ) : (
          <div className="field-row">
            <label className="microlabel" htmlFor="ckpt-select">
              checkpoint
            </label>
            <select
              id="ckpt-select"
              className="control"
              value={selectedId ?? ""}
              onChange={(e) => onSelect(e.target.value)}
            >
              <option value="" disabled>
                select checkpoint…
              </option>
              {checkpoints.map((c) => (
                <option key={c.id} value={c.id}>
                  ◈ {c.label ?? "(unlabeled)"} · {shortId(c.id)} · {fmtClock(c.created_at)}
                </option>
              ))}
            </select>
          </div>
        )}

        {loading && <div className="loading">reconstructing…</div>}
        {error && <div className="banner-error">{error}</div>}
        {stateAt && !loading && (
          <>
            <div className="microlabel" style={{ marginBottom: 8 }}>
              source: {stateAt.source} · seq ≤ {stateAt.checkpoint.event_seq}
            </div>
            {Object.keys(stateAt.state).length === 0 ? (
              <div className="state-empty">state was empty at this checkpoint</div>
            ) : (
              <JsonTree data={stateAt.state} />
            )}
          </>
        )}
      </div>
    </section>
  );
}
