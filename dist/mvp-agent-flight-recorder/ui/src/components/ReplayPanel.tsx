import { useState } from "react";
import { api } from "../api/client";
import type { Checkpoint, ReplayResult } from "../api/types";
import { shortId } from "../util/format";

const MODES = [
  { id: "dry_run", label: "dry_run — ticket only, nothing executes" },
  { id: "mock_tools", label: "mock_tools — handler runs, tools mocked" },
];

export function ReplayPanel({
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
  const [mode, setMode] = useState("dry_run");
  const [result, setResult] = useState<ReplayResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const replay = async () => {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.replay(runId, selectedId, mode));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel panel-ticks">
      <div className="panel-head">
        <span className="panel-title">Replay</span>
      </div>
      <div className="panel-body">
        <div className="field-row">
          <label className="microlabel" htmlFor="replay-ckpt">
            from checkpoint
          </label>
          <select
            id="replay-ckpt"
            className="control"
            value={selectedId ?? ""}
            onChange={(e) => onSelect(e.target.value)}
          >
            <option value="" disabled>
              select checkpoint…
            </option>
            {checkpoints.map((c) => (
              <option key={c.id} value={c.id}>
                ◈ {c.label ?? "(unlabeled)"} · {shortId(c.id)}
              </option>
            ))}
          </select>
        </div>
        <div className="field-row">
          <label className="microlabel" htmlFor="replay-mode">
            mode
          </label>
          <select
            id="replay-mode"
            className="control"
            value={mode}
            onChange={(e) => setMode(e.target.value)}
          >
            {MODES.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
        </div>

        <button className="btn btn-primary" disabled={!selectedId || busy} onClick={replay}>
          {busy ? "requesting…" : "▶ request replay ticket"}
        </button>

        {error && (
          <div className="banner-error" style={{ marginTop: 12 }}>
            {error}
          </div>
        )}
        {result && (
          <div className="replay-result">
            <div>
              status: <span className="ok">{result.status}</span> · mode: {result.mode}
            </div>
            <div style={{ marginTop: 6, color: "var(--text-dim)" }}>{result.message}</div>
            <div style={{ marginTop: 6 }} className="microlabel">
              resume via SDK handler or:
            </div>
            <div style={{ marginTop: 4, wordBreak: "break-all" }}>
              afr replay {shortId(runId)} --from {shortId(result.checkpoint_id)} --mode{" "}
              {result.mode === "dry_run" ? "mock_tools" : result.mode} --handler your.module:resume
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
