import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError, getApiToken, setApiToken } from "../api/client";
import type { Run } from "../api/types";
import { StatusPill } from "../components/StatusPill";
import { duration, fmtTime, shortId } from "../util/format";

const SDK_SNIPPET = `import afr

with afr.start_run("my-agent"):
    afr.log_model(model="gpt-x", input=prompt, output=answer)
    afr.log_tool("search", args={"q": "..."}, result=hits)
    afr.checkpoint("before-side-effect")`;

const STRIP_ORDER = ["model_call", "tool_call", "state_snapshot", "checkpoint", "error"] as const;
const STRIP_GLYPH: Record<string, string> = {
  model_call: "✦",
  tool_call: "⚙",
  state_snapshot: "≡",
  checkpoint: "◈",
  error: "⚠",
};

function CopyableCommand({ command }: { command: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    void navigator.clipboard?.writeText(command).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    });
  };
  return (
    <button className="copy-cmd" onClick={copy} title="copy to clipboard">
      <code>{command}</code>
      <span className="copy-hint">{copied ? "copied ✓" : "copy"}</span>
    </button>
  );
}

function OnboardingPanel({ onSeeded }: { onSeeded: (runId: string) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const seed = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await api.seedDemo();
      onSeeded(result.run.id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="onboarding">
      <p className="onboard-title">No runs recorded yet</p>
      <p className="onboard-lede">
        Agent Flight Recorder is the black box for your Python agents: every model call,
        tool call, state snapshot, and checkpoint lands here, ready to inspect and
        replay — without re-running side effects.
      </p>

      <div className="onboard-grid">
        <div className="onboard-card">
          <span className="microlabel">fastest — one click</span>
          <p>
            Seed <strong>checkout-agent-payment-timeout</strong>: a checkout agent reserves
            inventory, checkpoints, then the payment call times out. Walk the failure,
            then replay from <em>before the charge</em> with the payment tool safely mocked.
          </p>
          <button className="btn btn-primary" disabled={busy} onClick={() => void seed()}>
            {busy ? "seeding…" : "▶ Create a demo incident"}
          </button>
          {error && <div className="banner-error" style={{ marginTop: 10 }}>{error}</div>}
          <span className="microlabel" style={{ marginTop: 8 }}>or from a terminal</span>
          <CopyableCommand command="make demo-docker" />
        </div>

        <div className="onboard-card">
          <span className="microlabel">record your own agent</span>
          <pre className="onboard-snippet"><code>{SDK_SNIPPET}</code></pre>
          <span className="microlabel">unsure about your setup?</span>
          <CopyableCommand command="afr doctor" />
        </div>
      </div>
    </div>
  );
}

function TokenPrompt({ onSaved }: { onSaved: () => void }) {
  const [value, setValue] = useState(getApiToken() ?? "");
  return (
    <div className="panel panel-ticks token-prompt">
      <div className="panel-body">
        <p className="onboard-title" style={{ fontSize: 15 }}>This server requires an API token</p>
        <p className="state-empty">
          The backend was started with <code>AFR_API_TOKEN</code>. Paste the same token to
          read and write runs (stored only in this browser's localStorage).
        </p>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            className="control"
            style={{ flex: 1 }}
            type="password"
            placeholder="AFR_API_TOKEN value…"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                setApiToken(value);
                onSaved();
              }
            }}
          />
          <button
            className="btn btn-primary"
            onClick={() => {
              setApiToken(value);
              onSaved();
            }}
          >
            save token
          </button>
        </div>
      </div>
    </div>
  );
}

function EventStrip({ counts }: { counts: Record<string, number> }) {
  const present = STRIP_ORDER.filter((t) => (counts[t] ?? 0) > 0);
  if (present.length === 0) return <span className="dim">—</span>;
  return (
    <span className="event-strip">
      {present.map((t, i) => (
        <span key={t} className="strip-item" data-type={t} title={`${counts[t]} × ${t}`}>
          {i > 0 && <span className="strip-arrow">→</span>}
          {STRIP_GLYPH[t]}
          <span className="strip-count">{counts[t]}</span>
        </span>
      ))}
    </span>
  );
}

export default function RunListPage() {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [needsToken, setNeedsToken] = useState(false);
  const navigate = useNavigate();

  const load = (status: string, tag: string) => {
    api
      .listRuns({ status: status || undefined, tag: tag || undefined })
      .then((r) => {
        setRuns(r);
        setError(null);
        setNeedsToken(false);
      })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 401) setNeedsToken(true);
        else setError(String(e));
      });
  };

  useEffect(() => {
    load(statusFilter, tagFilter);
    const interval = setInterval(() => load(statusFilter, tagFilter), 5000);
    return () => clearInterval(interval);
  }, [statusFilter, tagFilter]);

  const metrics = useMemo(() => {
    if (!runs) return null;
    return {
      total: runs.length,
      failed: runs.filter((r) => r.status === "failed").length,
      checkpoints: runs.reduce((acc, r) => acc + (r.checkpoints_count ?? 0), 0),
      lastRun: runs.length > 0 ? fmtTime(runs[0].created_at) : "—",
    };
  }, [runs]);

  const filtering = statusFilter !== "" || tagFilter !== "";

  if (needsToken) {
    return (
      <main>
        <div className="page-head">
          <h1 className="page-title">Runs<span className="cursor" /></h1>
        </div>
        <TokenPrompt onSaved={() => load(statusFilter, tagFilter)} />
      </main>
    );
  }

  return (
    <main>
      <div className="page-head">
        <h1 className="page-title">
          Runs<span className="cursor" />
        </h1>
        <span className="microlabel">every recorded agent run, newest first</span>
      </div>

      {error && <div className="banner-error">backend unreachable: {error}</div>}

      {metrics && (runs?.length ?? 0) > 0 && (
        <div className="metric-row">
          <div className="metric-card">
            <span className="metric-value">{metrics.total}</span>
            <span className="microlabel">total runs</span>
          </div>
          <div className={`metric-card ${metrics.failed > 0 ? "metric-bad" : ""}`}>
            <span className="metric-value">{metrics.failed}</span>
            <span className="microlabel">failed runs</span>
          </div>
          <div className="metric-card metric-gold">
            <span className="metric-value">◈ {metrics.checkpoints}</span>
            <span className="microlabel">replay-ready checkpoints</span>
          </div>
          <div className="metric-card">
            <span className="metric-value metric-time">{metrics.lastRun}</span>
            <span className="microlabel">last run</span>
          </div>
        </div>
      )}

      <div className="manifest-controls">
        <span className="microlabel">filter</span>
        <select
          className="control"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">all statuses</option>
          <option value="running">running</option>
          <option value="completed">completed</option>
          <option value="failed">failed</option>
        </select>
        <input
          className="control"
          placeholder="tag…"
          value={tagFilter}
          onChange={(e) => setTagFilter(e.target.value)}
          style={{ width: 130 }}
        />
        {filtering && (
          <button
            className="btn btn-mini"
            onClick={() => {
              setStatusFilter("");
              setTagFilter("");
            }}
          >
            ✕ reset filters
          </button>
        )}
      </div>

      <section className="panel panel-ticks">
        {runs === null ? (
          <div className="loading">querying recorder…</div>
        ) : runs.length === 0 && filtering ? (
          <div className="empty-state">
            <p>No runs match this filter.</p>
            <button
              className="btn"
              onClick={() => {
                setStatusFilter("");
                setTagFilter("");
              }}
            >
              show all runs
            </button>
          </div>
        ) : runs.length === 0 ? (
          <OnboardingPanel onSeeded={(runId) => navigate(`/runs/${runId}`)} />
        ) : (
          <table className="manifest">
            <thead>
              <tr>
                <th>Run</th>
                <th>Status</th>
                <th>Started</th>
                <th>Duration</th>
                <th>Events</th>
                <th>Ckpts</th>
                <th>Timeline</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run, i) => (
                <tr
                  key={run.id}
                  style={{ "--i": i } as CSSProperties}
                  onClick={() => navigate(`/runs/${run.id}`)}
                >
                  <td className="run-name-cell">
                    <span className="run-name">
                      {run.parent_run_id && <span title="forked run">⑂ </span>}
                      {run.name}
                      {run.tags?.map((t) => (
                        <span key={t} className="tag tag-mini">
                          {t}
                        </span>
                      ))}
                    </span>
                    <span className="run-id">{shortId(run.id)}</span>
                    {run.last_error && (
                      <span className="run-error" title={run.last_error}>
                        ⚠ {run.last_error}
                      </span>
                    )}
                  </td>
                  <td>
                    <StatusPill status={run.status} />
                  </td>
                  <td className="dim">{fmtTime(run.created_at)}</td>
                  <td className="dim">{duration(run.created_at, run.ended_at)}</td>
                  <td>
                    <span className="chip">{run.events_count}</span>
                  </td>
                  <td>
                    <span className="chip">◈ {run.checkpoints_count}</span>
                  </td>
                  <td>
                    <EventStrip counts={run.event_type_counts ?? {}} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}
