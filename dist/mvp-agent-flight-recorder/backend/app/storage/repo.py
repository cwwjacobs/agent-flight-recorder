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


def insert_run(run_id: str, name: str, status: str, metadata: dict, created_at: str) -> dict:
    with connect() as conn:
        conn.execute(
            "INSERT INTO runs (id, name, status, metadata, created_at) VALUES (?, ?, ?, ?, ?)",
            (run_id, name, status, json.dumps(metadata), created_at),
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
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    sql = f"SELECT r.*, {_RUN_COUNTS} FROM runs r"
    params: list[Any] = []
    if status:
        sql += " WHERE r.status = ?"
        params.append(status)
    sql += " ORDER BY r.created_at DESC, r.id LIMIT ? OFFSET ?"
    params += [limit, offset]
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_run_row_to_dict(r) for r in rows]


def set_run_status(run_id: str, status: str, ended_at: str | None) -> dict | None:
    with connect() as conn:
        conn.execute(
            "UPDATE runs SET status = ?, ended_at = ? WHERE id = ?",
            (status, ended_at, run_id),
        )
        conn.commit()
    return get_run(run_id)


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
