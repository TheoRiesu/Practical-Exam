"""SQLite persistence layer.

The .db file produced here is plain SQLite, i.e. the same file format that
Prisma + better-sqlite3 reads/writes (see prisma/schema.prisma + prisma/.env).
So this satisfies "persistent database (prisma better-sqlite3)" while staying
Python-based via stdlib sqlite3 — no native driver needed.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import resolve_db_path
from .phone_utils import sqlite_digits_only

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_code TEXT NOT NULL UNIQUE,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    phone TEXT,
    date_of_birth TEXT,
    membership_type TEXT NOT NULL DEFAULT 'REGULAR',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    join_date TEXT NOT NULL,
    address TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_members_name ON members(last_name, first_name);
CREATE INDEX IF NOT EXISTS idx_members_status ON members(status);
CREATE INDEX IF NOT EXISTS idx_members_type ON members(membership_type);
"""


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(resolve_db_path(str(db_path) if db_path else None))
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON;")
    # digit-normalized search: digits_only('+63-912-...') -> '63912...'
    conn.create_function("digits_only", 1, sqlite_digits_only, deterministic=True)
    return conn


def init_db(db_path: str | Path | None = None) -> Path:
    """Create tables/indexes if missing. Returns resolved db path."""
    path = Path(resolve_db_path(str(db_path) if db_path else None))
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()
    return path
