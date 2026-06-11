from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


logger = logging.getLogger("experiment-service.database")

SQLITE_BUSY_TIMEOUT_MS = 5000


def connect_sqlite(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=SQLITE_BUSY_TIMEOUT_MS / 1000)
    connection.row_factory = sqlite3.Row
    _apply_pragmas(connection)
    return connection


def initialize_sqlite_database(db_path: Path, schema: str) -> None:
    with connect_sqlite(db_path) as connection:
        connection.executescript(schema)
        _verify_pragmas(connection)
    logger.info("[DATABASE] SQLITE_INITIALIZED path=%s", db_path)


def verify_sqlite_database(db_path: Path) -> dict[str, int | str]:
    with connect_sqlite(db_path) as connection:
        _verify_pragmas(connection)
        journal_mode = connection.execute("pragma journal_mode").fetchone()[0]
        foreign_keys = connection.execute("pragma foreign_keys").fetchone()[0]
        busy_timeout = connection.execute("pragma busy_timeout").fetchone()[0]
    return {
        "path": str(db_path),
        "journal_mode": str(journal_mode),
        "foreign_keys": int(foreign_keys),
        "busy_timeout": int(busy_timeout),
    }


@contextmanager
def sqlite_transaction(db_path: Path) -> Iterator[sqlite3.Connection]:
    connection = connect_sqlite(db_path)
    try:
        connection.execute("begin immediate")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def ensure_columns(db_path: Path, table_name: str, columns: dict[str, str]) -> None:
    with connect_sqlite(db_path) as connection:
        existing = {row["name"] for row in connection.execute(f"pragma table_info({table_name})").fetchall()}
        for column, definition in columns.items():
            if column not in existing:
                connection.execute(f"alter table {table_name} add column {column} {definition}")


def _apply_pragmas(connection: sqlite3.Connection) -> None:
    connection.execute("pragma journal_mode = wal")
    connection.execute(f"pragma busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
    connection.execute("pragma foreign_keys = on")


def _verify_pragmas(connection: sqlite3.Connection) -> None:
    foreign_keys = connection.execute("pragma foreign_keys").fetchone()[0]
    busy_timeout = connection.execute("pragma busy_timeout").fetchone()[0]
    if int(foreign_keys) != 1:
        raise RuntimeError("SQLite foreign_keys pragma is not enabled")
    if int(busy_timeout) < SQLITE_BUSY_TIMEOUT_MS:
        raise RuntimeError("SQLite busy_timeout pragma is below required threshold")
