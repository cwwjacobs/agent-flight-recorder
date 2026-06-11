export function StatusPill({ status }: { status: string }) {
  const cls =
    status === "running"
      ? "status-running"
      : status === "failed"
        ? "status-failed"
        : "status-completed";
  return (
    <span className={`status ${cls}`}>
      <span className="led" />
      {status}
    </span>
  );
}
