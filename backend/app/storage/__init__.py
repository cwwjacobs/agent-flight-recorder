"""SQLite storage layer.

- `db.py`   — connection management, schema, migrations
- `repo.py` — plain-function repository over the tables
"""

from app.storage.db import connect, db_path  # noqa: F401
