import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Checkpoint } from "../api/types";
import { usePremium } from "../license/LicenseContext";
import { fmtClock, shortId } from "../util/format";

export function CheckpointBrowser({
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
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [busyFork, setBusyFork] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fork = async (checkpointId: string) => {
    setBusyFork(checkpointId);
    setError(null);
    try {
      const created = await api.forkRun(runId, checkpointId);
      navigate(`/runs/${created.id}`);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusyFork(null);
    }
  };

  const visible = checkpoints.filter(
    (c) =>
      !query ||
      (c.label ?? "").toLowerCase().includes(query.toLowerCase()) ||
      c.id.startsWith(query)
  );

  return (
    <section className="panel panel-ticks">
      <div className="panel-head">
        <span className="panel-title">Checkpoints</span>
        <span className="microlabel" style={{ marginLeft: "auto" }}>
          {checkpoints.length}
        </span>
      </div>
      <div className="panel-body">
        {checkpoints.length === 0 ? (
          <div className="state-empty">no checkpoints in this run</div>
        ) : (
          <>
            {checkpoints.length > 3 && (
              <input
                className="control"
                style={{ width: "100%", marginBottom: 10 }}
                placeholder="filter checkpoints…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            )}
            <div className="ckpt-list">
              {visible.map((c) => (
                <div
                  key={c.id}
                  className={`ckpt-row ${selectedId === c.id ? "selected" : ""}`}
                  onClick={() => onSelect(c.id)}
                >
                  <span className="ckpt-glyph">◈</span>
                  <span className="ckpt-label">{c.label ?? "(unlabeled)"}</span>
                  <span className="ckpt-meta">
                    {shortId(c.id)} · {fmtClock(c.created_at)}
                  </span>
                  <span className="ckpt-actions">
                    {premium && (
                      <button
                        className="btn btn-mini"
                        disabled={busyFork === c.id}
                        title="fork a new run from this checkpoint"
                        onClick={(e) => {
                          e.stopPropagation();
                          void fork(c.id);
                        }}
                      >
                        {busyFork === c.id ? "…" : "⑂ fork"}
                      </button>
                    )}
                  </span>
                </div>
              ))}
            </div>
            {!premium && (
              <p className="state-empty" style={{ marginTop: 8 }}>
                🔒 forking from checkpoints is a premium feature
              </p>
            )}
            {error && <div className="banner-error">{error}</div>}
          </>
        )}
      </div>
    </section>
  );
}
