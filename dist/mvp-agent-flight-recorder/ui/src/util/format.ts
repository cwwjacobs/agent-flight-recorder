export function shortId(id: string | null | undefined, n = 8): string {
  return (id ?? "").slice(0, n);
}

export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function fmtClock(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/** elapsed offset between run start and an event, as T+SS.mmm */
export function tPlus(startIso: string, eventIso: string): string {
  const start = new Date(startIso).getTime();
  const at = new Date(eventIso).getTime();
  if (Number.isNaN(start) || Number.isNaN(at)) return "";
  const ms = Math.max(0, at - start);
  if (ms < 60_000) return `T+${(ms / 1000).toFixed(2)}s`;
  const m = Math.floor(ms / 60_000);
  const s = ((ms % 60_000) / 1000).toFixed(0).padStart(2, "0");
  return `T+${m}m${s}s`;
}

export function duration(startIso: string, endIso: string | null): string {
  if (!endIso) return "…";
  const ms = new Date(endIso).getTime() - new Date(startIso).getTime();
  if (Number.isNaN(ms) || ms < 0) return "—";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60_000)}m ${Math.round((ms % 60_000) / 1000)}s`;
}
