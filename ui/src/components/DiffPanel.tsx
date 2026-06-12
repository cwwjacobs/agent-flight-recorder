import { useMemo, useState } from "react";
import type { AfrEvent } from "../api/types";
import { usePremium } from "../license/LicenseContext";
import { collectStatePoints, diffJson, foldStateUpTo } from "../util/jsondiff";

function Val({ v }: { v: unknown }) {
  const text = JSON.stringify(v);
  return <span className="diff-val">{text && text.length > 80 ? text.slice(0, 79) + "…" : text}</span>;
}

export function DiffPanel({ events }: { events: AfrEvent[] }) {
  const premium = usePremium();
  const points = useMemo(() => collectStatePoints(events), [events]);
  const [seqA, setSeqA] = useState<number | "">("");
  const [seqB, setSeqB] = useState<number | "">("");

  const entries = useMemo(() => {
    if (seqA === "" || seqB === "") return null;
    return diffJson(foldStateUpTo(events, seqA), foldStateUpTo(events, seqB));
  }, [events, seqA, seqB]);

  if (!premium) {
    return (
      <section className="panel panel-ticks">
        <div className="panel-head">
          <span className="panel-title">Compare State</span>
          <span className="lock-chip">🔒 premium</span>
        </div>
        <div className="panel-body">
          <p className="state-empty">
            Compare agent state between any two checkpoints or snapshots.
            Set <code>AFR_PREMIUM_ENABLED=true</code> to unlock.
          </p>
        </div>
      </section>
    );
  }

  const counts = entries
    ? {
        added: entries.filter((e) => e.kind === "added").length,
        removed: entries.filter((e) => e.kind === "removed").length,
        changed: entries.filter((e) => e.kind === "changed").length,
      }
    : null;

  return (
    <section className="panel panel-ticks">
      <div className="panel-head">
        <span className="panel-title">Compare State</span>
        {counts && (
          <span className="microlabel" style={{ marginLeft: "auto" }}>
            <span className="diff-added">+{counts.added}</span>{" "}
            <span className="diff-removed">−{counts.removed}</span>{" "}
            <span className="diff-changed">~{counts.changed}</span>
          </span>
        )}
      </div>
      <div className="panel-body">
        {points.length < 2 ? (
          <div className="state-empty">
            Records at least two state points (snapshots or checkpoints) and this panel
            shows exactly what changed between them — added, removed, and changed keys.
          </div>
        ) : (
          <>
            <div className="field-row">
              <label className="microlabel">from (A)</label>
              <select
                className="control"
                value={seqA}
                onChange={(e) => setSeqA(e.target.value === "" ? "" : Number(e.target.value))}
              >
                <option value="">select…</option>
                {points.map((p) => (
                  <option key={p.seq} value={p.seq}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="field-row">
              <label className="microlabel">to (B)</label>
              <select
                className="control"
                value={seqB}
                onChange={(e) => setSeqB(e.target.value === "" ? "" : Number(e.target.value))}
              >
                <option value="">select…</option>
                {points.map((p) => (
                  <option key={p.seq} value={p.seq}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>

            {!entries && (
              <div className="state-empty">
                pick two points (A = before, B = after) to see what changed between them
              </div>
            )}
            {entries && entries.length === 0 && (
              <div className="state-empty">states are identical</div>
            )}
            {entries && entries.length > 0 && (
              <div className="diff-list">
                {entries.map((entry, i) => (
                  <div key={i} className={`diff-row diff-${entry.kind}`}>
                    <span className="diff-kind">
                      {entry.kind === "added" ? "+" : entry.kind === "removed" ? "−" : "~"}
                    </span>
                    <span className="diff-path">{entry.path}</span>
                    <span className="diff-values">
                      {entry.kind !== "added" && <Val v={entry.before} />}
                      {entry.kind === "changed" && <span className="diff-arrow"> → </span>}
                      {entry.kind !== "removed" && <Val v={entry.after} />}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
