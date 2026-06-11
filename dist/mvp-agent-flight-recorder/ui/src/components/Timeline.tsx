import { useState } from "react";
import type { CSSProperties } from "react";
import type { AfrEvent, Run } from "../api/types";
import { JsonTree } from "./JsonTree";
import { tPlus } from "../util/format";

export function isErrorEvent(e: AfrEvent): boolean {
  return e.event_type === "error" || (e.payload as { status?: string }).status === "error";
}

function EventCard({
  event,
  run,
  index,
  onInspectCheckpoint,
}: {
  event: AfrEvent;
  run: Run;
  index: number;
  onInspectCheckpoint?: (checkpointId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const failed = isErrorEvent(event);
  const isCheckpoint = event.event_type === "checkpoint";
  const checkpointId = isCheckpoint
    ? ((event.payload as { checkpoint_id?: string }).checkpoint_id ?? null)
    : null;
  const durationMs = (event.payload as { duration_ms?: number }).duration_ms;

  return (
    <div
      className={`tl-event ${failed ? "is-error" : ""} ${open ? "open" : ""}`}
      data-type={event.event_type}
      style={{ "--i": index } as CSSProperties}
    >
      <span className="tl-node" />
      <div className="tl-card">
        <button className="tl-row" onClick={() => setOpen((v) => !v)}>
          <span className="tl-seq">#{String(event.seq).padStart(3, "0")}</span>
          <span className="tl-type">{event.event_type.replace("_", " ")}</span>
          <span className="tl-name">{event.name ?? "—"}</span>
          {failed && <span className="tl-status-err">FAIL</span>}
          {typeof durationMs === "number" && (
            <span className="tl-duration">{durationMs.toFixed(0)}ms</span>
          )}
          <span className="tl-time">{tPlus(run.created_at, event.created_at)}</span>
          <span className="tl-caret">▸</span>
        </button>
        {open && (
          <div className="tl-payload">
            <JsonTree data={event.payload} />
          </div>
        )}
        {isCheckpoint && checkpointId && onInspectCheckpoint && (
          <div className="tl-ckpt-actions">
            <button className="btn" onClick={() => onInspectCheckpoint(checkpointId)}>
              ◈ view state
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export function Timeline({
  events,
  run,
  onInspectCheckpoint,
}: {
  events: AfrEvent[];
  run: Run;
  onInspectCheckpoint?: (checkpointId: string) => void;
}) {
  if (events.length === 0) {
    return <div className="state-empty">no events recorded yet</div>;
  }
  return (
    <div className="timeline">
      {events.map((e, i) => (
        <EventCard
          key={e.id}
          event={e}
          run={run}
          index={i}
          onInspectCheckpoint={onInspectCheckpoint}
        />
      ))}
    </div>
  );
}
