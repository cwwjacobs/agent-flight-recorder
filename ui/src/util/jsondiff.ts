/** Structural JSON diff + client-side state folding (mirrors backend semantics). */

import type { AfrEvent } from "../api/types";

export interface DiffEntry {
  path: string;
  kind: "added" | "removed" | "changed";
  before?: unknown;
  after?: unknown;
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function deepEqual(a: unknown, b: unknown): boolean {
  if (Object.is(a, b)) return true;
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((v, i) => deepEqual(v, b[i]));
  }
  if (isPlainObject(a) && isPlainObject(b)) {
    const ka = Object.keys(a);
    const kb = Object.keys(b);
    return ka.length === kb.length && ka.every((k) => k in b && deepEqual(a[k], b[k]));
  }
  return false;
}

export function diffJson(a: unknown, b: unknown, path = "$"): DiffEntry[] {
  if (deepEqual(a, b)) return [];
  if (isPlainObject(a) && isPlainObject(b)) {
    const entries: DiffEntry[] = [];
    for (const key of new Set([...Object.keys(a), ...Object.keys(b)])) {
      const sub = `${path}.${key}`;
      if (!(key in b)) entries.push({ path: sub, kind: "removed", before: a[key] });
      else if (!(key in a)) entries.push({ path: sub, kind: "added", after: b[key] });
      else entries.push(...diffJson(a[key], b[key], sub));
    }
    return entries;
  }
  if (Array.isArray(a) && Array.isArray(b)) {
    const entries: DiffEntry[] = [];
    const max = Math.max(a.length, b.length);
    for (let i = 0; i < max; i++) {
      const sub = `${path}[${i}]`;
      if (i >= b.length) entries.push({ path: sub, kind: "removed", before: a[i] });
      else if (i >= a.length) entries.push({ path: sub, kind: "added", after: b[i] });
      else entries.push(...diffJson(a[i], b[i], sub));
    }
    return entries;
  }
  return [{ path, kind: "changed", before: a, after: b }];
}

function deepMerge(
  base: Record<string, unknown>,
  patch: Record<string, unknown>
): Record<string, unknown> {
  const out: Record<string, unknown> = { ...base };
  for (const [key, value] of Object.entries(patch)) {
    const existing = out[key];
    if (isPlainObject(value) && isPlainObject(existing)) {
      out[key] = deepMerge(existing, value);
    } else {
      out[key] = value;
    }
  }
  return out;
}

/** Fold state_snapshot events up to (and including) a seq — same algorithm
 * as the backend's engine/state.py, so the diff viewer can compute state at
 * any point without extra round-trips. */
export function foldStateUpTo(events: AfrEvent[], uptoSeq: number): Record<string, unknown> {
  let state: Record<string, unknown> = {};
  for (const event of events) {
    if (event.seq > uptoSeq) break;
    if (event.event_type !== "state_snapshot") continue;
    const payload = event.payload as { state?: unknown; mode?: string };
    if (!isPlainObject(payload.state)) continue;
    state = payload.mode === "merge" ? deepMerge(state, payload.state) : payload.state;
  }
  return state;
}

/** Points a user can diff between: every checkpoint and state snapshot. */
export interface StatePoint {
  seq: number;
  label: string;
  kind: "checkpoint" | "snapshot";
}

export function collectStatePoints(events: AfrEvent[]): StatePoint[] {
  const points: StatePoint[] = [];
  for (const e of events) {
    if (e.event_type === "checkpoint") {
      const label = (e.payload as { label?: string }).label ?? e.name ?? "checkpoint";
      points.push({ seq: e.seq, label: `◈ ${label} (#${e.seq})`, kind: "checkpoint" });
    } else if (e.event_type === "state_snapshot") {
      points.push({ seq: e.seq, label: `▤ ${e.name ?? "state"} (#${e.seq})`, kind: "snapshot" });
    }
  }
  return points;
}
