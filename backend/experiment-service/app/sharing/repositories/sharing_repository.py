from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from app.core.database import connect_sqlite, initialize_sqlite_database, sqlite_transaction


SHARING_SCHEMA = """
create table if not exists sharing_trust (
    source_type text not null,
    source_id text not null,
    trusted integer not null,
    updated_at text not null,
    primary key (source_type, source_id)
);

create table if not exists sharing_analytics (
    metric text primary key,
    value integer not null
);

create table if not exists sharing_package_hashes (
    package_hash text primary key,
    manifest_hash text not null,
    revision_hash text not null,
    direction text not null,
    manifest_id text,
    recorded_at text not null
);

create index if not exists idx_sharing_package_manifest_hash
on sharing_package_hashes(manifest_hash);
"""


class SharingRepository:
    METRICS = ("imports", "exports", "trusted_sources", "verification_failures")

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or Path(__file__).resolve().parents[2] / "storage" / "sharing.sqlite3"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def set_trust(self, source_type: str, source_id: str, trusted: bool, updated_at: str) -> dict[str, Any]:
        with sqlite_transaction(self.db_path) as connection:
            connection.execute(
                """
                insert into sharing_trust (source_type, source_id, trusted, updated_at)
                values (?, ?, ?, ?)
                on conflict(source_type, source_id)
                do update set trusted = excluded.trusted, updated_at = excluded.updated_at
                """,
                (source_type, source_id, 1 if trusted else 0, updated_at),
            )
            if trusted:
                self._set_metric(connection, "trusted_sources", self._count_trusted(connection))
            return {
                "source_type": source_type,
                "source_id": source_id,
                "trusted": trusted,
                "updated_at": updated_at,
            }

    def is_trusted(self, source_type: str, source_id: str) -> bool:
        if not source_id:
            return False
        with sqlite_transaction(self.db_path) as connection:
            row = connection.execute(
                "select trusted from sharing_trust where source_type = ? and source_id = ?",
                (source_type, source_id),
            ).fetchone()
            return bool(row and row["trusted"])

    def increment(self, metric: str, amount: int = 1) -> None:
        if metric not in self.METRICS:
            return
        with sqlite_transaction(self.db_path) as connection:
            current = self._metric(connection, metric)
            self._set_metric(connection, metric, current + amount)

    def analytics(self) -> dict[str, int]:
        with self._connect() as connection:
            return {metric: self._metric(connection, metric) for metric in self.METRICS}

    def record_package_hash(
        self,
        package_hash: str,
        manifest_hash: str,
        revision_hash: str,
        direction: str,
        manifest_id: str | None,
        recorded_at: str,
    ) -> None:
        with sqlite_transaction(self.db_path) as connection:
            connection.execute(
                """
                insert into sharing_package_hashes (
                    package_hash, manifest_hash, revision_hash, direction, manifest_id, recorded_at
                )
                values (?, ?, ?, ?, ?, ?)
                on conflict(package_hash)
                do update set
                    manifest_hash = excluded.manifest_hash,
                    revision_hash = excluded.revision_hash,
                    direction = excluded.direction,
                    manifest_id = excluded.manifest_id,
                    recorded_at = excluded.recorded_at
                """,
                (package_hash, manifest_hash, revision_hash, direction, manifest_id, recorded_at),
            )

    def _metric(self, connection: sqlite3.Connection, metric: str) -> int:
        row = connection.execute("select value from sharing_analytics where metric = ?", (metric,)).fetchone()
        return int(row["value"]) if row else 0

    def _set_metric(self, connection: sqlite3.Connection, metric: str, value: int) -> None:
        connection.execute(
            """
            insert into sharing_analytics (metric, value)
            values (?, ?)
            on conflict(metric) do update set value = excluded.value
            """,
            (metric, value),
        )

    def _count_trusted(self, connection: sqlite3.Connection) -> int:
        row = connection.execute("select count(*) as total from sharing_trust where trusted = 1").fetchone()
        return int(row["total"]) if row else 0

    def _connect(self) -> sqlite3.Connection:
        return connect_sqlite(self.db_path)

    def _initialize(self) -> None:
        initialize_sqlite_database(self.db_path, SHARING_SCHEMA)
        with sqlite_transaction(self.db_path) as connection:
            for metric in self.METRICS:
                self._set_metric(connection, metric, self._metric(connection, metric))
