import { useState } from "react";
import { api } from "../api/client";
import type { Checkpoint, ReplayResult } from "../api/types";
import { usePremium } from "../license/LicenseContext";
import { shortId } from "../util/format";

const MODES = [
  {
    id: "dry_run",
    label: "dry_run — plan only",
    help: "Builds the replay plan and reconstructs state. Nothing runs — not even your resume handler.",
    premium: false,
  },
  {
    id: "mock_tools",
    label: "mock_tools — everything mocked",
    help: "Your resume handler runs, but every tool returns its recorded result instead of executing. The safest way to actually step through a failure.",
    premium: false,
  },
  {
    id: "allow_safe_tools",
    label: "allow_safe_tools — read-only tools execute",
    help: "Tools recorded as policy \"safe\" (read-only) really execute; everything else is mocked.",
    premium: true,
  },
  {
    id: "allow_side_effects",
    label: "allow_side_effects — side effects execute",
    help: "Side-effecting tools really execute. Tools marked requires_approval stay blocked unless you approve them below.",
    premium: true,
  },
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
    <section className="panel panel-ticks" id="replay-panel">
      <div className="panel-head">
        <span className="panel-title">Replay Plan</span>
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

        <p className="mode-help">{MODES.find((m) => m.id === mode)?.help}</p>

        {mode === "allow_side_effects" && (
          <div className="warn-banner">
            ⚠ This mode re-executes real side effects (charges, writes, emails) when your
            resume handler runs. Use it only when that is exactly what you want.
          </div>
        )}

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
          {busy ? "preparing…" : "▶ Prepare replay plan"}
        </button>
        {!selectedId && (
          <p className="mode-help" style={{ marginTop: 8 }}>
            select a checkpoint above (or press “replay from here” on one) to enable this
          </p>
        )}

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
            {plan.length > 0 && <div className="microlabel" style={{ marginTop: 8 }}>tool safety plan</div>}
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
            {plan.length > 0 && (
              <div className="plan-legend">
                allow = really executes · mock = recorded result, no execution ·
                skip = plan only · block = refused (needs approval)
              </div>
            )}
            {result.policy_notes && (
              <div style={{ marginTop: 6, color: "var(--text-dim)" }}>{result.policy_notes}</div>
            )}
            <div style={{ marginTop: 8, color: "var(--text-dim)" }}>
              The server only prepares this plan and state — it never executes your code.
              Your resume handler enforces it (use <code>ctx.call_tool(...)</code> from the SDK).
            </div>
            <div style={{ marginTop: 8 }} className="microlabel">
              resume from your terminal:
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
