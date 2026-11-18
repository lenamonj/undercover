"""The UnderCover database: SQLite, seeded from data/ when empty."""

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent.parent / "data"
DEFAULT_DB = Path(__file__).parent / "undercover.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'waiting',
    decision TEXT,
    payout REAL,
    reason TEXT,
    policy_section TEXT,
    paid_amount REAL,
    signed_off_by TEXT,
    thread_id TEXT
);
CREATE TABLE IF NOT EXISTS policies (policy_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS customers (customer_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS handlers (handler_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS steps (
    step_id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT NOT NULL REFERENCES claims (claim_id),
    kind TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
"""


def db_path() -> Path:
    """Return the database file, from UNDERCOVER_DB if set."""
    return Path(os.getenv("UNDERCOVER_DB", str(DEFAULT_DB)))


def load(name: str) -> Any:
    """Load one JSON file from data/."""
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Open a connection, commit on success and always close."""
    conn = sqlite3.connect(db_path(), check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Create the tables, and seed them from data/ if the queue is empty."""
    with connect() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        if conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]:
            return
        tables = {
            "claims": ("claim_id", "claims.json"),
            "policies": ("policy_id", "policies.json"),
            "customers": ("customer_id", "customers.json"),
            "handlers": ("handler_id", "handlers.json"),
        }
        for table, (key, file) in tables.items():
            conn.executemany(
                f"INSERT INTO {table} ({key}, data) VALUES (?, ?)",  # noqa: S608
                [(row[key], json.dumps(row)) for row in load(file)],
            )


def reset() -> None:
    """Delete the database and seed a fresh one."""
    for suffix in ("", "-wal", "-shm"):
        Path(f"{db_path()}{suffix}").unlink(missing_ok=True)
    init_db()


if __name__ == "__main__":
    reset()
    print(f"Reset {db_path()}")
