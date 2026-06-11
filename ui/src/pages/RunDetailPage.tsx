import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { AfrEvent, Checkpoint, Run } from "../api/types";
import { ReplayPanel } from "../components/ReplayPanel";
import { StatePanel } from "../components/StatePanel";
import { StatusPill } from "../components/StatusPill";
import { Timeline } from "../components/Timeline";
import { duration, fmtTime, shortId } from "../util/format";

export default function RunDetailPage() {
  const { runId = "" } = useParams();
  const [run, setRun] = useState<Run | null>(null);
  const [events, setEvents] = useState<AfrEvent[]>([]);
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([]);
  const [selectedCkpt, setSelectedCkpt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    Promise.all([api.getRun(runId), api.getEvents(runId), api.getCheckpoints(runId)])
      .then(([r, ev, cks]) => {
        setRun(r);
        setEvents(ev);
        setCheckpoints(cks);
        setError(null);
      })
      .catch((e) => setError(String(e)));
  }, [runId]);

  useEffect(() => {
    load();
  }, [load]);

  // live-follow running runs
  useEffect(() => {
    if (run?.status !== "running") return;
    const interval = setInterval(load, 4000);
    return () => clearInterval(interval);
  }, [run?.status, load]);

  if (error) {
    return (
      <main>
        <Link className="back-link" to="/">
          ← manifest
        </Link>
        <div className="banner-error" style={{ marginTop: 16 }}>
          {error}
        </div>
      </main>
    );
  }

  if (!run) return <div className="loading">loading run…</div>;

  const errorCount = events.filter(
    (e) => e.event_type === "error" || (e.payload as { status?: string }).status === "error"
  ).length;

  return (
    <main>
      <Link className="back-link" to="/">
        ← manifest
      </Link>

      <div className="page-head" style={{ marginTop: 10 }}>
        <h1 className="page-title">{run.name}</h1>
        <StatusPill status={run.status} />
      </div>

      <section className="panel panel-ticks run-meta">
        <div className="meta-item">
          <span className="microlabel">run id</span>
          <span className="meta-value">{run.id}</span>
        </div>
        <div className="meta-item">
          <span className="microlabel">started</span>
          <span className="meta-value">{fmtTime(run.created_at)}</span>
        </div>
        <div className="meta-item">
          <span className="microlabel">duration</span>
          <span className="meta-value">{duration(run.created_at, run.ended_at)}</span>
        </div>
        <div className="meta-item">
          <span className="microlabel">events</span>
          <span className="meta-value">{run.events_count}</span>
        </div>
        <div className="meta-item">
          <span className="microlabel">checkpoints</span>
          <span className="meta-value">◈ {run.checkpoints_count}</span>
        </div>
        {errorCount > 0 && (
          <div className="meta-item">
            <span className="microlabel">failures</span>
            <span className="meta-value" style={{ color: "var(--danger)" }}>
              ⚠ {errorCount}
            </span>
          </div>
        )}
      </section>

      <div className="run-layout">
        <section className="panel panel-ticks">
          <div className="panel-head">
            <span className="panel-title">Timeline</span>
            <span className="microlabel" style={{ marginLeft: "auto" }}>
              {events.length} events
            </span>
          </div>
          <div className="panel-body">
            <Timeline events={events} run={run} onInspectCheckpoint={setSelectedCkpt} />
          </div>
        </section>

        <aside className="inspector">
          <StatePanel
            runId={run.id}
            checkpoints={checkpoints}
            selectedId={selectedCkpt}
            onSelect={setSelectedCkpt}
          />
          <ReplayPanel
            runId={run.id}
            checkpoints={checkpoints}
            selectedId={selectedCkpt}
            onSelect={setSelectedCkpt}
          />
          {run.metadata && Object.keys(run.metadata).length > 0 && (
            <section className="panel panel-ticks">
              <div className="panel-head">
                <span className="panel-title">Metadata</span>
              </div>
              <div className="panel-body">
                <div className="json-tree">
                  {Object.entries(run.metadata).map(([k, v]) => (
                    <div key={k}>
                      <span className="jt-key">{k}</span>
                      <span className="jt-punct">: </span>
                      <span className="jt-string">{JSON.stringify(v)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          )}
        </aside>
      </div>

      <p className="microlabel" style={{ marginTop: 14 }}>
        run {shortId(run.id)} · inspect via CLI: afr runs show {shortId(run.id)}
      </p>
    </main>
  );
}
