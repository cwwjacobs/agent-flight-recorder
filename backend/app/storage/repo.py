"""Repository functions over the SQLite schema.

All functions open a short-lived connection, do their work, and return plain
dicts with JSON columns already decoded. Events are append-only: there is no
update or delete path for the events table by design.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.storage.db import connect

# ---------------------------------------------------------------------------
# helpers


def _loads(text: str | None, fallback: Any) -> Any:
    if not text:
        return fallback
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return fallback


def _run_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["metadata"] = _loads(d.get("metadata"), {})
    d["tags"] = _loads(d.get("tags"), [])
    return d


def _event_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["payload"] = _loads(d.get("payload"), {})
    return d


def _checkpoint_row_to_dict(row: sqlite3.Row, include_state: bool = False) -> dict[str, Any]:
    d = dict(row)
    if include_state:
        d["state"] = _loads(d.get("state"), {})
    else:
        d.pop("state", None)
    return d


_RUN_COUNTS = """
    (SELECT COUNT(*) FROM events e WHERE e.run_id = r.id)      AS events_count,
    (SELECT COUNT(*) FROM checkpoints c WHERE c.run_id = r.id) AS checkpoints_count
"""

# ---------------------------------------------------------------------------
# runs


def insert_run(
    run_id: str,
    name: str,
    status: str,
    metadata: dict,
    created_at: str,
    parent_run_id: str | None = None,
    fork_checkpoint_id: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    with connect() as conn:
        conn.execute(
            "INSERT INTO runs (id, name, status, metadata, created_at, parent_run_id,"
            " fork_checkpoint_id, tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                name,
                status,
                json.dumps(metadata),
                created_at,
                parent_run_id,
                fork_checkpoint_id,
                json.dumps(tags or []),
            ),
        )
        conn.commit()
    return get_run(run_id)  # type: ignore[return-value]


def get_run(run_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            f"SELECT r.*, {_RUN_COUNTS} FROM runs r WHERE r.id = ?", (run_id,)
        ).fetchone()
    return _run_row_to_dict(row) if row else None


def list_runs(
    status: str | None = None,
    tag: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    sql = f"SELECT r.*, {_RUN_COUNTS} FROM runs r"
    where: list[str] = []
    params: list[Any] = []
    if status:
        where.append("r.status = ?")
        params.append(status)
    if tag:
        where.append("EXISTS (SELECT 1 FROM json_each(r.tags) je WHERE je.value = ?)")
        params.append(tag)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY r.created_at DESC, r.id LIMIT ? OFFSET ?"
    params += [limit, offset]
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_run_row_to_dict(r) for r in rows]


def update_run_fields(
    run_id: str,
    name: str | None = None,
    tags: list[str] | None = None,
    notes: str | None = None,
) -> dict | None:
    sets: list[str] = []
    params: list[Any] = []
    if name is not None:
        sets.append("name = ?")
        params.append(name)
    if tags is not None:
        sets.append("tags = ?")
        params.append(json.dumps(tags))
    if notes is not None:
        sets.append("notes = ?")
        params.append(notes)
    if sets:
        params.append(run_id)
        with connect() as conn:
            conn.execute(f"UPDATE runs SET {', '.join(sets)} WHERE id = ?", params)
            conn.commit()
    return get_run(run_id)


def list_forks(parent_run_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            f"SELECT r.*, {_RUN_COUNTS} FROM runs r WHERE r.parent_run_id = ?"
            " ORDER BY r.created_at",
            (parent_run_id,),
        ).fetchall()
    return [_run_row_to_dict(r) for r in rows]


def set_run_status(run_id: str, status: str, ended_at: str | None) -> dict | None:
    with connect() as conn:
        conn.execute(
            "UPDATE runs SET status = ?, ended_at = ? WHERE id = ?",
            (status, ended_at, run_id),
        )
        conn.commit()
    return get_run(run_id)


def last_errors_for_runs(run_ids: list[str]) -> dict[str, str | None]:
    """Latest error-event message per run (for run-list summaries)."""
    if not run_ids:
        return {}
    placeholders = ",".join("?" * len(run_ids))
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT e.run_id, e.payload FROM events e
            JOIN (
                SELECT run_id, MAX(seq) AS max_seq FROM events
                WHERE event_type = 'error' AND run_id IN ({placeholders})
                GROUP BY run_id
            ) latest ON e.run_id = latest.run_id AND e.seq = latest.max_seq
            """,
            run_ids,
        ).fetchall()
    return {row["run_id"]: _loads(row["payload"], {}).get("message") for row in rows}


def event_type_counts_for_runs(run_ids: list[str]) -> dict[str, dict[str, int]]:
    """{run_id: {event_type: count}} (for run-list event strips)."""
    if not run_ids:
        return {}
    placeholders = ",".join("?" * len(run_ids))
    with connect() as conn:
        rows = conn.execute(
            f"SELECT run_id, event_type, COUNT(*) AS n FROM events"
            f" WHERE run_id IN ({placeholders}) GROUP BY run_id, event_type",
            run_ids,
        ).fetchall()
    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        counts.setdefault(row["run_id"], {})[row["event_type"]] = row["n"]
    return counts


# ---------------------------------------------------------------------------
# events (append-only)


def insert_event(
    event_id: str,
    run_id: str,
    event_type: str,
    name: str | None,
    payload: dict,
    created_at: str,
) -> dict:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO events (id, run_id, event_type, name, payload, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (event_id, run_id, event_type, name, json.dumps(payload), created_at),
        )
        seq = cur.lastrowid
        conn.commit()
        row = conn.execute("SELECT * FROM events WHERE seq = ?", (seq,)).fetchone()
    return _event_row_to_dict(row)


def list_events(
    run_id: str,
    event_type: str | None = None,
    limit: int = 1000,
    offset: int = 0,
    up_to_seq: int | None = None,
) -> list[dict]:
    sql = "SELECT * FROM events WHERE run_id = ?"
    params: list[Any] = [run_id]
    if event_type:
        sql += " AND event_type = ?"
        params.append(event_type)
    if up_to_seq is not None:
        sql += " AND seq <= ?"
        params.append(up_to_seq)
    sql += " ORDER BY seq LIMIT ? OFFSET ?"
    params += [limit, offset]
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_event_row_to_dict(r) for r in rows]


def get_event(event_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    return _event_row_to_dict(row) if row else None


# ---------------------------------------------------------------------------
# checkpoints


def insert_checkpoint(
    checkpoint_id: str,
    run_id: str,
    event_id: str,
    event_seq: int,
    label: str | None,
    state: dict,
    created_at: str,
) -> dict:
    with connect() as conn:
        conn.execute(
            "INSERT INTO checkpoints (id, run_id, event_id, event_seq, label, state, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (checkpoint_id, run_id, event_id, event_seq, label, json.dumps(state), created_at),
        )
        conn.commit()
    return get_checkpoint(checkpoint_id, include_state=True)  # type: ignore[return-value]


def get_checkpoint(checkpoint_id: str, include_state: bool = False) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM checkpoints WHERE id = ?", (checkpoint_id,)
        ).fetchone()
    return _checkpoint_row_to_dict(row, include_state) if row else None


def list_checkpoints(run_id: str, include_state: bool = False) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM checkpoints WHERE run_id = ? ORDER BY event_seq", (run_id,)
        ).fetchall()
    return [_checkpoint_row_to_dict(r, include_state) for r in rows]
