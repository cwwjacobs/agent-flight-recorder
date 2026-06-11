import { useState } from "react";
import type { KeyboardEvent } from "react";
import { api } from "../api/client";
import type { Run } from "../api/types";
import { usePremium } from "../license/LicenseContext";

export function TagsNotes({ run, onUpdated }: { run: Run; onUpdated: (r: Run) => void }) {
  const premium = usePremium();
  const [draft, setDraft] = useState("");
  const [notes, setNotes] = useState(run.notes ?? "");
  const [savingNotes, setSavingNotes] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const saveTags = async (tags: string[]) => {
    try {
      onUpdated(await api.updateRun(run.id, { tags }));
      setError(null);
    } catch (e) {
      setError(String(e));
    }
  };

  const onTagKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && draft.trim()) {
      e.preventDefault();
      void saveTags([...(run.tags ?? []), draft.trim()]);
      setDraft("");
    }
  };

  const saveNotes = async () => {
    setSavingNotes(true);
    try {
      onUpdated(await api.updateRun(run.id, { notes }));
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setSavingNotes(false);
    }
  };

  return (
    <section className="panel panel-ticks">
      <div className="panel-head">
        <span className="panel-title">Tags &amp; Notes</span>
        {!premium && <span className="lock-chip">🔒 premium</span>}
      </div>
      <div className="panel-body">
        <div className="field-row">
          <label className="microlabel">tags</label>
          <div className="tag-row">
            {(run.tags ?? []).map((tag) => (
              <span key={tag} className="tag">
                {tag}
                {premium && (
                  <button
                    className="tag-x"
                    title={`remove ${tag}`}
                    onClick={() => void saveTags((run.tags ?? []).filter((t) => t !== tag))}
                  >
                    ×
                  </button>
                )}
              </span>
            ))}
            {premium ? (
              <input
                className="control tag-input"
                placeholder="add tag ⏎"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={onTagKey}
              />
            ) : (
              (run.tags ?? []).length === 0 && <span className="state-empty">none</span>
            )}
          </div>
        </div>

        <div className="field-row">
          <label className="microlabel">notes</label>
          {premium ? (
            <>
              <textarea
                className="control"
                rows={4}
                placeholder="What happened on this run?"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
              <button
                className="btn"
                disabled={savingNotes || notes === (run.notes ?? "")}
                onClick={() => void saveNotes()}
              >
                {savingNotes ? "saving…" : "save notes"}
              </button>
            </>
          ) : (
            <div className="state-empty">{run.notes || "—"}</div>
          )}
        </div>

        {error && <div className="banner-error">{error}</div>}
        {!premium && (
          <p className="state-empty">
            Set <code>AFR_PREMIUM_ENABLED=true</code> to tag and annotate runs.
          </p>
        )}
      </div>
    </section>
  );
}
