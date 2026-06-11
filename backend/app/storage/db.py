"""SQLite connection management and schema migrations.

Schema versioning uses PRAGMA user_version: each entry in MIGRATIONS is an
idempotent script; on connect we apply any entries past the stored version.
Connections are cheap (per-request) and WAL mode keeps readers and the
single writer from blocking each other.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from app import config

_migrate_lock = threading.Lock()

MIGRATIONS: list[str] = [
    # v1 — MVP schema: runs, append-only events, checkpoints
    """
    CREATE TABLE IF NOT EXISTS runs (
        id          TEXT PRIMARY KEY,
        name        TEXT NOT NULL,
        status      TEXT NOT NULL DEFAULT 'running',
        metadata    TEXT NOT NULL DEFAULT '{}',
        created_at  TEXT NOT NULL,
        ended_at    TEXT
    );

    CREATE TABLE IF NOT EXISTS events (
        seq         INTEGER PRIMARY KEY AUTOINCREMENT,
        id          TEXT NOT NULL UNIQUE,
        run_id      TEXT NOT NULL REFERENCES runs(id),
        event_type  TEXT NOT NULL,
        name        TEXT,
        payload     TEXT NOT NULL DEFAULT '{}',
        created_at  TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_events_run_id      ON events(run_id);
    CREATE INDEX IF NOT EXISTS idx_events_created_at  ON events(created_at);
    CREATE INDEX IF NOT EXISTS idx_events_event_type  ON events(event_type);
    CREATE INDEX IF NOT EXISTS idx_events_run_created ON events(run_id, created_at);
    CREATE INDEX IF NOT EXISTS idx_events_run_type    ON events(run_id, event_type);

    CREATE TABLE IF NOT EXISTS checkpoints (
        id          TEXT PRIMARY KEY,
        run_id      TEXT NOT NULL REFERENCES runs(id),
        event_id    TEXT NOT NULL,
        event_seq   INTEGER NOT NULL,
        label       TEXT,
        state       TEXT NOT NULL DEFAULT '{}',
        created_at  TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_checkpoints_run_id ON checkpoints(run_id);
    """,
    # v2 — Premium: run tags/notes and fork lineage
    """
    ALTER TABLE runs ADD COLUMN tags TEXT NOT NULL DEFAULT '[]';
    ALTER TABLE runs ADD COLUMN notes TEXT NOT NULL DEFAULT '';
    ALTER TABLE runs ADD COLUMN parent_run_id TEXT;
    ALTER TABLE runs ADD COLUMN fork_checkpoint_id TEXT;

    CREATE INDEX IF NOT EXISTS idx_runs_parent ON runs(parent_run_id);
    """,
]


def db_path() -> str:
    return config.db_path()


def connect() -> sqlite3.Connection:
    path = db_path()
    if path != ":memory:":
        parent = Path(path).expanduser().parent
        if str(parent) not in ("", "."):
            parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    with _migrate_lock:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version >= len(MIGRATIONS):
            return
        for i in range(version, len(MIGRATIONS)):
            conn.executescript(MIGRATIONS[i])
            conn.execute(f"PRAGMA user_version = {i + 1}")
        conn.commit()
