"""SQLite connection and schema initialization for SANAD Core.

Single entry point for opening a database — every other module gets its
connection from here, never opens sqlite3 directly, so pragmas/row_factory
stay consistent everywhere.
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def new_id() -> str:
    """A stable UUID4 string — used for every primary key in this project."""
    return str(uuid.uuid4())


def now_iso() -> str:
    """UTC timestamp in ISO-8601, used for every created_at/updated_at."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: str | Path = ":memory:") -> sqlite3.Connection:
    """Open a connection with the schema applied and sane defaults set.

    :memory: is the default deliberately — tests and one-off tooling should
    never touch a real library file unless a path is explicitly given.

    check_same_thread=False: FastAPI runs sync dependencies (get_conn) in a
    threadpool while an async endpoint body runs on the loop thread, so one
    request's connection is legitimately touched from two threads — but always
    sequentially, never concurrently (each request opens and closes its own
    connection). This flag permits that; it is not a license for shared/
    concurrent use across requests.
    """
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Apply schema.sql. Safe to call repeatedly (every statement is
    CREATE TABLE/INDEX IF NOT EXISTS)."""
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(sql)
    conn.commit()


def table_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return sorted(r["name"] for r in rows)
