from __future__ import annotations

import json
import sqlite3
import hashlib
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.models.manifest_storage import ExperimentStatus
from app.core.database import connect_sqlite, ensure_columns, initialize_sqlite_database, sqlite_transaction
from app.storage.sqlite_schema import BUILDER_SQLITE_SCHEMA


class ManifestStorageRepository:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or Path(__file__).resolve().parent / "builder_manifests.sqlite3"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def create(
        self,
        manifest_id: str,
        owner_id: str,
        title: str,
        manifest: dict[str, Any],
        execution: dict[str, Any] | None,
        created_at: str,
    ) -> dict[str, Any]:
        manifest_hash = self.content_hash(manifest)
        with sqlite_transaction(self.db_path) as connection:
            connection.execute(
                """
                insert into experiment_manifests (
                    id, owner_id, title, description, subject, status,
                    manifest_version, current_revision, content_hash, manifest_hash, created_at, updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    manifest_id,
                    owner_id,
                    title,
                    manifest.get("description"),
                    manifest.get("subject"),
                    ExperimentStatus.DRAFT.value,
                    manifest.get("manifest_version"),
                    1,
                    manifest_hash,
                    manifest_hash,
                    created_at,
                    created_at,
                ),
            )
            self._insert_revision(connection, manifest_id, 1, manifest, execution, created_at, owner_id)
            self._replace_tags(connection, manifest_id, manifest.get("tags", []))
        return self.get(manifest_id) or {}

    def update(
        self,
        manifest_id: str,
        owner_id: str | None,
        title: str | None,
        manifest: dict[str, Any],
        execution: dict[str, Any] | None,
        updated_at: str,
    ) -> dict[str, Any] | None:
        existing = self.get(manifest_id)
        if existing is None:
            return None
        next_revision = int(existing["current_revision"]) + 1
        next_title = title or str(manifest.get("title") or existing["title"])
        manifest_hash = self.content_hash(manifest)
        with sqlite_transaction(self.db_path) as connection:
            connection.execute(
                """
                update experiment_manifests
                set owner_id = coalesce(?, owner_id),
                    title = ?,
                    description = ?,
                    subject = ?,
                    manifest_version = ?,
                    current_revision = ?,
                    content_hash = ?,
                    manifest_hash = ?,
                    updated_at = ?
                where id = ?
                """,
                (
                    owner_id,
                    next_title,
                    manifest.get("description"),
                    manifest.get("subject"),
                    manifest.get("manifest_version"),
                    next_revision,
                    manifest_hash,
                    manifest_hash,
                    updated_at,
                    manifest_id,
                ),
            )
            self._insert_revision(connection, manifest_id, next_revision, manifest, execution, updated_at, owner_id)
            self._replace_tags(connection, manifest_id, manifest.get("tags", []))
        return self.get(manifest_id)

    def delete(self, manifest_id: str) -> bool:
        with sqlite_transaction(self.db_path) as connection:
            connection.execute("delete from experiment_tags where manifest_id = ?", (manifest_id,))
            connection.execute("delete from experiment_revisions where manifest_id = ?", (manifest_id,))
            cursor = connection.execute("delete from experiment_manifests where id = ?", (manifest_id,))
            return cursor.rowcount > 0

    def publish(self, manifest_id: str, updated_at: str) -> dict[str, Any] | None:
        return self._set_status(manifest_id, ExperimentStatus.PUBLISHED, updated_at)

    def archive(self, manifest_id: str, updated_at: str) -> dict[str, Any] | None:
        return self._set_status(manifest_id, ExperimentStatus.ARCHIVED, updated_at)

    def list(self, owner_id: str | None = None) -> list[dict[str, Any]]:
        query = "select * from experiment_manifests"
        params: tuple[Any, ...] = ()
        if owner_id:
            query += " where owner_id = ?"
            params = (owner_id,)
        query += " order by updated_at desc"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
            return [self._manifest_row(row, connection) for row in rows]

    def get(self, manifest_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("select * from experiment_manifests where id = ?", (manifest_id,)).fetchone()
            if row is None:
                return None
            return self._manifest_row(row, connection)

    def find_by_manifest_hash(self, manifest_hash: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                select *
                from experiment_manifests
                where manifest_hash = ? or content_hash = ?
                order by updated_at desc
                limit 1
                """,
                (manifest_hash, manifest_hash),
            ).fetchone()
            if row is None:
                return None
            return self._manifest_row(row, connection)

    def revisions(self, manifest_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                select id, manifest_id, revision, revision_hash, created_at, created_by
                from experiment_revisions
                where manifest_id = ?
                order by revision asc
                """,
                (manifest_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def load_revision(self, manifest_id: str, revision: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                select *
                from experiment_revisions
                where manifest_id = ? and revision = ?
                """,
                (manifest_id, revision),
            ).fetchone()
            if row is None:
                return None
            return self._revision_row(row)

    def save_revision(
        self,
        manifest_id: str,
        revision: int,
        manifest: dict[str, Any],
        execution: dict[str, Any] | None,
        created_at: str,
        created_by: str | None,
    ) -> dict[str, Any]:
        with sqlite_transaction(self.db_path) as connection:
            self._insert_revision(connection, manifest_id, revision, manifest, execution, created_at, created_by)
        loaded = self.load_revision(manifest_id, revision)
        return loaded or {}

    def import_draft(
        self,
        manifest_id: str,
        owner_id: str,
        title: str,
        manifest: dict[str, Any],
        revisions: list[dict[str, Any]],
        created_at: str,
    ) -> dict[str, Any]:
        current_revision = max([int(item.get("revision", 1)) for item in revisions] or [1])
        manifest_hash = self.content_hash(manifest)
        with sqlite_transaction(self.db_path) as connection:
            connection.execute(
                """
                insert into experiment_manifests (
                    id, owner_id, title, description, subject, status,
                    manifest_version, current_revision, content_hash, manifest_hash, created_at, updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    manifest_id,
                    owner_id,
                    title,
                    manifest.get("description"),
                    manifest.get("subject"),
                    ExperimentStatus.DRAFT.value,
                    manifest.get("manifest_version"),
                    current_revision,
                    manifest_hash,
                    manifest_hash,
                    created_at,
                    created_at,
                ),
            )
            if revisions:
                for item in revisions:
                    self._insert_revision(
                        connection,
                        manifest_id,
                        int(item.get("revision", 1)),
                        item.get("manifest") if isinstance(item.get("manifest"), dict) else manifest,
                        item.get("execution") if isinstance(item.get("execution"), dict) else None,
                        str(item.get("created_at") or created_at),
                        item.get("created_by"),
                    )
            else:
                self._insert_revision(connection, manifest_id, 1, manifest, None, created_at, owner_id)
            self._replace_tags(connection, manifest_id, manifest.get("tags", []))
        return self.get(manifest_id) or {}

    def _set_status(self, manifest_id: str, status: ExperimentStatus, updated_at: str) -> dict[str, Any] | None:
        with sqlite_transaction(self.db_path) as connection:
            cursor = connection.execute(
                "update experiment_manifests set status = ?, updated_at = ? where id = ?",
                (status.value, updated_at, manifest_id),
            )
            if cursor.rowcount == 0:
                return None
        return self.get(manifest_id)

    def _insert_revision(
        self,
        connection: sqlite3.Connection,
        manifest_id: str,
        revision: int,
        manifest: dict[str, Any],
        execution: dict[str, Any] | None,
        created_at: str,
        created_by: str | None,
    ) -> None:
        connection.execute(
            """
            insert into experiment_revisions (
                id, manifest_id, revision, manifest_json, execution_json, revision_hash, created_at, created_by
            )
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                manifest_id,
                revision,
                json.dumps(manifest, sort_keys=True),
                json.dumps(execution, sort_keys=True) if execution is not None else None,
                self.revision_hash(manifest, execution),
                created_at,
                created_by,
            ),
        )

    def _replace_tags(self, connection: sqlite3.Connection, manifest_id: str, tags: Any) -> None:
        connection.execute("delete from experiment_tags where manifest_id = ?", (manifest_id,))
        if not isinstance(tags, list):
            return
        for tag in tags:
            if str(tag).strip():
                connection.execute(
                    "insert into experiment_tags (id, manifest_id, tag) values (?, ?, ?)",
                    (str(uuid4()), manifest_id, str(tag)),
                )

    def _manifest_row(self, row: sqlite3.Row, connection: sqlite3.Connection) -> dict[str, Any]:
        data = dict(row)
        tags = connection.execute(
            "select tag from experiment_tags where manifest_id = ? order by tag asc",
            (data["id"],),
        ).fetchall()
        data["tags"] = [tag_row["tag"] for tag_row in tags]
        return data

    def _revision_row(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["manifest"] = json.loads(data.pop("manifest_json") or "{}")
        execution_json = data.pop("execution_json")
        data["execution"] = json.loads(execution_json) if execution_json else None
        return data

    def _connect(self) -> sqlite3.Connection:
        return connect_sqlite(self.db_path)

    def _initialize(self) -> None:
        initialize_sqlite_database(self.db_path, BUILDER_SQLITE_SCHEMA)
        ensure_columns(self.db_path, "experiment_manifests", {"content_hash": "text", "manifest_hash": "text"})
        ensure_columns(self.db_path, "experiment_revisions", {"revision_hash": "text"})
        with sqlite_transaction(self.db_path) as connection:
            connection.execute(
                "create index if not exists idx_builder_manifests_manifest_hash on experiment_manifests(manifest_hash)"
            )
            connection.execute(
                "create index if not exists idx_builder_revisions_hash on experiment_revisions(revision_hash)"
            )
            self._backfill_hashes(connection)

    def content_hash(self, manifest: dict[str, Any]) -> str:
        payload = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def revision_hash(self, manifest: dict[str, Any], execution: dict[str, Any] | None) -> str:
        payload = {
            "manifest": manifest,
            "execution": execution,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        ).hexdigest()

    def _backfill_hashes(self, connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            """
            select id, content_hash
            from experiment_manifests
            where manifest_hash is null or manifest_hash = ''
            """
        ).fetchall()
        for row in rows:
            if row["content_hash"]:
                connection.execute(
                    "update experiment_manifests set manifest_hash = ? where id = ?",
                    (row["content_hash"], row["id"]),
                )

        revision_rows = connection.execute(
            """
            select id, manifest_json, execution_json
            from experiment_revisions
            where revision_hash is null or revision_hash = ''
            """
        ).fetchall()
        for row in revision_rows:
            manifest = json.loads(row["manifest_json"] or "{}")
            execution = json.loads(row["execution_json"]) if row["execution_json"] else None
            connection.execute(
                "update experiment_revisions set revision_hash = ? where id = ?",
                (self.revision_hash(manifest, execution), row["id"]),
            )
