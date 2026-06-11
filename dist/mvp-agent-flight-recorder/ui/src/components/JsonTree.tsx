/** Collapsible, syntax-coloured JSON tree. Strings equal to the backend's
 * redaction marker render as a clearly visible REDACTED chip. */

const REDACTED_MARKER = "[REDACTED]";

function Value({ value, depth }: { value: unknown; depth: number }) {
  if (value === null) return <span className="jt-null">null</span>;
  if (typeof value === "boolean") return <span className="jt-bool">{String(value)}</span>;
  if (typeof value === "number") return <span className="jt-number">{String(value)}</span>;
  if (typeof value === "string") {
    if (value === REDACTED_MARKER) {
      return (
        <span className="jt-redacted" title="value redacted by AFR">
          ⛨ redacted
        </span>
      );
    }
    return <span className="jt-string">"{value}"</span>;
  }
  if (Array.isArray(value)) return <ArrayNode items={value} depth={depth} />;
  if (typeof value === "object") {
    return <ObjectNode obj={value as Record<string, unknown>} depth={depth} />;
  }
  return <span className="jt-string">{String(value)}</span>;
}

function ArrayNode({ items, depth }: { items: unknown[]; depth: number }) {
  if (items.length === 0) return <span className="jt-punct">[]</span>;
  return (
    <details open={depth < 2}>
      <summary>
        <span className="jt-punct">[</span>
        <span className="jt-count">{items.length} items</span>
      </summary>
      <div>
        {items.map((item, i) => (
          <div key={i}>
            <Value value={item} depth={depth + 1} />
            {i < items.length - 1 && <span className="jt-punct">,</span>}
          </div>
        ))}
      </div>
      <span className="jt-punct">]</span>
    </details>
  );
}

function ObjectNode({ obj, depth }: { obj: Record<string, unknown>; depth: number }) {
  const keys = Object.keys(obj);
  if (keys.length === 0) return <span className="jt-punct">{"{}"}</span>;
  return (
    <details open={depth < 2}>
      <summary>
        <span className="jt-punct">{"{"}</span>
        <span className="jt-count">{keys.length} keys</span>
      </summary>
      <div>
        {keys.map((key, i) => (
          <div key={key}>
            <span className="jt-key">{key}</span>
            <span className="jt-punct">: </span>
            <Value value={obj[key]} depth={depth + 1} />
            {i < keys.length - 1 && <span className="jt-punct">,</span>}
          </div>
        ))}
      </div>
      <span className="jt-punct">{"}"}</span>
    </details>
  );
}

export function JsonTree({ data }: { data: unknown }) {
  return (
    <div className="json-tree">
      <Value value={data} depth={0} />
    </div>
  );
}
