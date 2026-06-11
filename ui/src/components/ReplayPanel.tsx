import { useState } from "react";
import { api } from "../api/client";
import type { Checkpoint, ReplayResult } from "../api/types";
import { usePremium } from "../license/LicenseContext";
import { shortId } from "../util/format";

const MODES = [
  { id: "dry_run", label: "dry_run — ticket only, nothing executes", premium: false },
  { id: "mock_tools", label: "mock_tools — handler runs, all tools mocked", premium: false },
  { id: "allow_safe_tools", label: "allow_safe_tools — safe tools execute", premium: true },
  { id: "allow_side_effects", label: "allow_side_effects — full execution", premium: true },
];

const ACTION_CLASS: Record<string, string> = {
  allow: "plan-allow",
  mock: "plan-mock",
  skip: "plan-skip",
  block: "plan-block",
};

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
  const premium = usePremium();
  const [mode, setMode] = useState("dry_run");
  const [approved, setApproved] = useState(false);
  const [result, setResult] = useState<ReplayResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const replay = async () => {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.replay(runId, selectedId, mode, approved));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const plan = result ? Object.entries(result.tool_plan) : [];

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
            safety mode
          </label>
          <select
            id="replay-mode"
            className="control"
            value={mode}
            onChange={(e) => setMode(e.target.value)}
          >
            {MODES.map((m) => (
              <option key={m.id} value={m.id} disabled={m.premium && !premium}>
                {m.premium && !premium ? `🔒 ${m.label}` : m.label}
              </option>
            ))}
          </select>
        </div>

        {mode === "allow_side_effects" && (
          <label className="approve-row">
            <input
              type="checkbox"
              checked={approved}
              onChange={(e) => setApproved(e.target.checked)}
            />
            <span>
              approve <code>requires_approval</code> tools (otherwise they are blocked)
            </span>
          </label>
        )}

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
            {plan.length > 0 && (
              <table className="plan-table">
                <thead>
                  <tr>
                    <th>tool</th>
                    <th>policy</th>
                    <th>action</th>
                  </tr>
                </thead>
                <tbody>
                  {plan.map(([tool, entry]) => (
                    <tr key={tool}>
                      <td>{tool}</td>
                      <td>{entry.policy}</td>
                      <td>
                        <span className={`plan-action ${ACTION_CLASS[entry.action] ?? ""}`}>
                          {entry.action}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {result.policy_notes && (
              <div style={{ marginTop: 6, color: "var(--text-dim)" }}>{result.policy_notes}</div>
            )}
            <div style={{ marginTop: 8 }} className="microlabel">
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
