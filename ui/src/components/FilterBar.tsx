import type { EventType } from "../api/types";

const TYPES: { id: EventType; label: string }[] = [
  { id: "model_call", label: "model" },
  { id: "tool_call", label: "tool" },
  { id: "state_snapshot", label: "state" },
  { id: "checkpoint", label: "ckpt" },
  { id: "log", label: "log" },
  { id: "error", label: "error" },
];

export interface TimelineFilter {
  types: Set<string>;
  errorsOnly: boolean;
}

export const EMPTY_FILTER: TimelineFilter = { types: new Set(), errorsOnly: false };

export function FilterBar({
  filter,
  onChange,
  shown,
  total,
}: {
  filter: TimelineFilter;
  onChange: (f: TimelineFilter) => void;
  shown: number;
  total: number;
}) {
  const toggleType = (id: string) => {
    const types = new Set(filter.types);
    if (types.has(id)) types.delete(id);
    else types.add(id);
    onChange({ ...filter, types });
  };

  return (
    <div className="filter-bar">
      <span className="microlabel">show</span>
      {TYPES.map((t) => (
        <button
          key={t.id}
          data-type={t.id}
          className={`filter-chip ${filter.types.size === 0 || filter.types.has(t.id) ? "on" : ""}`}
          onClick={() => toggleType(t.id)}
          title={t.id}
        >
          {t.label}
        </button>
      ))}
      <button
        className={`filter-chip errors ${filter.errorsOnly ? "on" : ""}`}
        onClick={() => onChange({ ...filter, errorsOnly: !filter.errorsOnly })}
      >
        ⚠ failures only
      </button>
      <span className="microlabel" style={{ marginLeft: "auto" }}>
        {shown}/{total}
      </span>
    </div>
  );
}
