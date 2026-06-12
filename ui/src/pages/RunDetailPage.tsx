import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { AfrEvent, Checkpoint, Run } from "../api/types";
import { CheckpointBrowser } from "../components/CheckpointBrowser";
import { DiffPanel } from "../components/DiffPanel";
import { EMPTY_FILTER, FilterBar } from "../components/FilterBar";
import type { TimelineFilter } from "../components/FilterBar";
import { ReplayPanel } from "../components/ReplayPanel";
import { StatePanel } from "../components/StatePanel";
import { StatusPill } from "../components/StatusPill";
import { TagsNotes } from "../components/TagsNotes";
import { Timeline, isErrorEvent } from "../components/Timeline";
import { duration, fmtTime, shortId } from "../util/format";

export default function RunDetailPage() {
  const { runId = "" } = useParams();
  const [run, setRun] = useState<Run | null>(null);
  const [events, setEvents] = useState<AfrEvent[]>([]);
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([]);
  const [selectedCkpt, setSelectedCkpt] = useState<string | null>(null);
  const [filter, setFilter] = useState<TimelineFilter>(EMPTY_FILTER);
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
    setRun(null);
    setSelectedCkpt(null);
    setFilter(EMPTY_FILTER);
    load();
  }, [load]);

  // live-follow running runs
  useEffect(() => {
    if (run?.status !== "running") return;
    const interval = setInterval(load, 4000);
    return () => clearInterval(interval);
  }, [run?.status, load]);

  const visibleEvents = useMemo(
    () =>
      events.filter((e) => {
        if (filter.errorsOnly && !isErrorEvent(e)) return false;
        if (filter.types.size > 0 && !filter.types.has(e.event_type)) return false;
        return true;
      }),
    [events, filter]
  );

  if (error) {
    return (
      <main>
        <Link className="back-link" to="/">
          ← all runs
        </Link>
        <div className="banner-error" style={{ marginTop: 16 }}>
          {error}
        </div>
      </main>
    );
  }

  if (!run) return <div className="loading">loading run…</div>;

  const errorCount = events.filter(isErrorEvent).length;
  const lastError = [...events].reverse().find((e) => e.event_type === "error");
  const lastErrorMessage =
    lastError ? String((lastError.payload as { message?: string }).message ?? "") : null;

  const summaryLine =
    run.status === "failed"
      ? `Run failed${lastErrorMessage ? ` — ${lastErrorMessage}` : ""}`
      : run.status === "running"
        ? "Run in progress — recording live"
        : `Run completed${errorCount > 0 ? ` (${errorCount} recovered failure${errorCount > 1 ? "s" : ""} along the way)` : ""}`;

  return (
    <main>
      <Link className="back-link" to="/">
        ← all runs
      </Link>

      <div className="page-head" style={{ marginTop: 10 }}>
        <h1 className="page-title">{run.name}</h1>
        <StatusPill status={run.status} />
        {run.tags?.map((t) => (
          <span key={t} className="tag">
            {t}
          </span>
        ))}
      </div>

      <div className={`run-summary ${run.status === "failed" ? "is-failed" : ""}`}>
        <span className="summary-line">{summaryLine}</span>
        <span className="summary-sub">
          {checkpoints.length > 0 ? (
            <>
              <span className="gold">◈ {checkpoints.length} checkpoint{checkpoints.length > 1 ? "s" : ""}</span>
              {" — replay-ready: pick one below and press “Prepare replay plan”"}
            </>
          ) : (
            "no checkpoints recorded — add afr.checkpoint(\"label\") before risky steps to make this run replayable"
          )}
        </span>
      </div>

      {run.parent_run_id && (
        <div className="lineage-banner">
          ⑂ forked from{" "}
          <Link to={`/runs/${run.parent_run_id}`}>{shortId(run.parent_run_id)}</Link> @ checkpoint{" "}
          {shortId(run.fork_checkpoint_id)}
        </div>
      )}
      {run.forks && run.forks.length > 0 && (
        <div className="lineage-banner">
          ⑂ forks:{" "}
          {run.forks.map((f, i) => (
            <span key={f.id}>
              {i > 0 && ", "}
              <Link to={`/runs/${f.id}`}>
                {f.name} ({shortId(f.id)})
              </Link>
            </span>
          ))}
        </div>
      )}

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
            <FilterBar
              filter={filter}
              onChange={setFilter}
              shown={visibleEvents.length}
              total={events.length}
            />
            <Timeline events={visibleEvents} run={run} onInspectCheckpoint={setSelectedCkpt} />
          </div>
        </section>

        <aside className="inspector">
          <CheckpointBrowser
            runId={run.id}
            checkpoints={checkpoints}
            selectedId={selectedCkpt}
            onSelect={setSelectedCkpt}
          />
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
          <DiffPanel events={events} />
          <TagsNotes run={run} onUpdated={setRun} />
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
        run {shortId(run.id)} · CLI: afr runs show {shortId(run.id)} · afr events {shortId(run.id)}
      </p>
    </main>
  );
}
