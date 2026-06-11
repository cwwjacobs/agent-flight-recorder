import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Run } from "../api/types";
import { StatusPill } from "../components/StatusPill";
import { duration, fmtTime, shortId } from "../util/format";

const EMPTY_GLYPH = `┌──────────────────────────────┐
│  ▲  FLIGHT RECORDER ARMED    │
│     no runs on the manifest  │
└──────────────────────────────┘`;

export default function RunListPage() {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const load = (status: string) => {
    api
      .listRuns(status ? { status } : undefined)
      .then((r) => {
        setRuns(r);
        setError(null);
      })
      .catch((e) => setError(String(e)));
  };

  useEffect(() => {
    load(statusFilter);
    const interval = setInterval(() => load(statusFilter), 5000);
    return () => clearInterval(interval);
  }, [statusFilter]);

  return (
    <main>
      <div className="page-head">
        <h1 className="page-title">
          Run Manifest<span className="cursor" />
        </h1>
        <span className="microlabel">{runs ? `${runs.length} recorded` : ""}</span>
      </div>

      {error && <div className="banner-error">backend unreachable: {error}</div>}

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
      </div>

      <section className="panel panel-ticks">
        {runs === null ? (
          <div className="loading">querying recorder…</div>
        ) : runs.length === 0 ? (
          <div className="empty-state">
            <div className="glyph">{EMPTY_GLYPH}</div>
            <p>
              Record your first run: <code>python examples/toy_agent/toy_agent.py</code>
            </p>
          </div>
        ) : (
          <table className="manifest">
            <thead>
              <tr>
                <th>Run</th>
                <th>ID</th>
                <th>Status</th>
                <th>Started</th>
                <th>Duration</th>
                <th>Events</th>
                <th>Ckpts</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run, i) => (
                <tr
                  key={run.id}
                  style={{ "--i": i } as CSSProperties}
                  onClick={() => navigate(`/runs/${run.id}`)}
                >
                  <td className="run-name">{run.name}</td>
                  <td className="run-id">{shortId(run.id)}</td>
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
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}
