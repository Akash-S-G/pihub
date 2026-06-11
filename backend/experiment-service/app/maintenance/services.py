from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from typing import Any, Callable

from app.core.database import connect_sqlite
from app.core.observability import log_slow_query
from app.storage.manifest_storage_repository import ManifestStorageRepository
from app.sharing.repositories.sharing_repository import SharingRepository
from app.classroom.repositories.classroom_repository import ClassroomRepository


class HashAuditService:
    def __init__(
        self,
        manifest_repository: ManifestStorageRepository | None = None,
        sharing_repository: SharingRepository | None = None,
    ) -> None:
        self.manifest_repository = manifest_repository or ManifestStorageRepository()
        self.sharing_repository = sharing_repository or SharingRepository()

    def audit(self) -> dict[str, Any]:
        warnings: list[str] = []
        failures: list[str] = []
        manifest_count = 0
        revision_count = 0
        package_count = 0

        with connect_sqlite(self.manifest_repository.db_path) as connection:
            manifests = connection.execute("select id, content_hash, manifest_hash from experiment_manifests").fetchall()
            manifest_count = len(manifests)
            for row in manifests:
                if not row["manifest_hash"]:
                    warnings.append(f"manifest missing manifest_hash: {row['id']}")
                if row["content_hash"] and row["manifest_hash"] and row["content_hash"] != row["manifest_hash"]:
                    failures.append(f"manifest content_hash mismatch: {row['id']}")

            revisions = connection.execute(
                "select id, manifest_id, revision, manifest_json, execution_json, revision_hash from experiment_revisions"
            ).fetchall()
            revision_count = len(revisions)
            for row in revisions:
                manifest = json.loads(row["manifest_json"] or "{}")
                execution = json.loads(row["execution_json"]) if row["execution_json"] else None
                expected = self.manifest_repository.revision_hash(manifest, execution)
                if not row["revision_hash"]:
                    warnings.append(f"revision missing revision_hash: {row['manifest_id']}#{row['revision']}")
                elif row["revision_hash"] != expected:
                    failures.append(f"revision_hash mismatch: {row['manifest_id']}#{row['revision']}")

        with connect_sqlite(self.sharing_repository.db_path) as connection:
            packages = connection.execute(
                """
                select package_hash, manifest_hash, revision_hash, manifest_id
                from sharing_package_hashes
                """
            ).fetchall()
            package_count = len(packages)
            for row in packages:
                for field in ("package_hash", "manifest_hash", "revision_hash"):
                    if not row[field]:
                        failures.append(f"package missing {field}: {row['package_hash'] or '<empty>'}")

        status = "INTEGRITY_FAILED" if failures else "INTEGRITY_WARNING" if warnings else "INTEGRITY_OK"
        return {
            "status": status,
            "manifest_count": manifest_count,
            "revision_count": revision_count,
            "package_count": package_count,
            "warnings": warnings,
            "failures": failures,
        }


class IntegrityScanner:
    def __init__(
        self,
        manifest_repository: ManifestStorageRepository | None = None,
        sharing_repository: SharingRepository | None = None,
        classroom_repository: ClassroomRepository | None = None,
    ) -> None:
        self.manifest_repository = manifest_repository or ManifestStorageRepository()
        self.sharing_repository = sharing_repository or SharingRepository()
        self.classroom_repository = classroom_repository or ClassroomRepository()

    def scan(self) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        with connect_sqlite(self.manifest_repository.db_path) as connection:
            self._append_count(
                issues,
                "experiment_revisions",
                "revisions_without_manifests",
                connection.execute(
                    """
                    select count(*) as total
                    from experiment_revisions r
                    left join experiment_manifests m on m.id = r.manifest_id
                    where m.id is null
                    """
                ).fetchone()["total"],
                "Delete orphan revisions or restore the missing manifest.",
            )

        with connect_sqlite(self.classroom_repository.db_path) as connection:
            self._append_count(
                issues,
                "classroom_assignments",
                "assignments_without_sessions",
                connection.execute(
                    """
                    select count(*) as total
                    from classroom_assignments a
                    left join classroom_sessions s on s.session_id = a.session_id
                    where s.session_id is null
                    """
                ).fetchone()["total"],
                "Archive or recreate assignments after restoring classroom sessions.",
            )
            self._append_count(
                issues,
                "classroom_submissions",
                "submissions_without_assignments",
                connection.execute(
                    """
                    select count(*) as total
                    from classroom_submissions sub
                    left join classroom_assignments a on a.assignment_id = sub.assignment_id
                    where a.assignment_id is null
                    """
                ).fetchone()["total"],
                "Reject or reattach orphan submissions before analytics export.",
            )

        with connect_sqlite(self.sharing_repository.db_path) as connection:
            self._append_count(
                issues,
                "sharing_package_hashes",
                "packages_without_manifest_id",
                connection.execute(
                    """
                    select count(*) as total
                    from sharing_package_hashes
                    where manifest_id is null or manifest_id = ''
                    """
                ).fetchone()["total"],
                "Retain package rows for audit, but avoid using them for sync until linked.",
            )

        return {
            "orphan_count": sum(issue["count"] for issue in issues),
            "affected_tables": [issue["table"] for issue in issues if issue["count"] > 0],
            "issues": issues,
            "repair_recommendations": [issue["repair_recommendation"] for issue in issues if issue["count"] > 0],
        }

    def _append_count(
        self,
        issues: list[dict[str, Any]],
        table: str,
        issue: str,
        count: int,
        recommendation: str,
    ) -> None:
        issues.append(
            {
                "table": table,
                "issue": issue,
                "count": int(count),
                "repair_recommendation": recommendation,
            }
        )


class DatabaseMaintenanceService:
    def __init__(self, db_paths: dict[str, Path] | None = None) -> None:
        self.db_paths = db_paths or {
            "builder": ManifestStorageRepository().db_path,
            "sharing": SharingRepository().db_path,
            "classroom": ClassroomRepository().db_path,
        }

    def health(self) -> dict[str, Any]:
        databases = {name: self._database_health(path) for name, path in self.db_paths.items()}
        return {
            "databases": databases,
            "total_database_size_mb": round(sum(item["database_size_mb"] for item in databases.values()), 4),
            "total_wal_size_mb": round(sum(item["wal_size_mb"] for item in databases.values()), 4),
        }

    def optimize(self) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for name, path in self.db_paths.items():
            with connect_sqlite(path) as connection:
                connection.execute("pragma optimize")
            results[name] = "ok"
        return results

    def _database_health(self, path: Path) -> dict[str, Any]:
        with connect_sqlite(path) as connection:
            tables = [
                row["name"]
                for row in connection.execute(
                    "select name from sqlite_master where type = 'table' and name not like 'sqlite_%'"
                ).fetchall()
            ]
            row_counts: dict[str, int] = {}
            for table in tables:
                start = time.perf_counter()
                row_counts[table] = int(connection.execute(f"select count(*) as total from {table}").fetchone()["total"])
                log_slow_query(table, "count_rows", (time.perf_counter() - start) * 1000)
            largest_tables = sorted(row_counts.items(), key=lambda item: item[1], reverse=True)[:5]
        wal_path = Path(f"{path}-wal")
        return {
            "path": str(path),
            "database_size_mb": self._size_mb(path),
            "wal_size_mb": self._size_mb(wal_path),
            "row_counts": row_counts,
            "largest_tables": [{"table": table, "rows": rows} for table, rows in largest_tables],
        }

    def _size_mb(self, path: Path) -> float:
        return round((path.stat().st_size / (1024 * 1024)), 4) if path.exists() else 0.0


class ClassroomConsistencyService:
    def __init__(self, repository: ClassroomRepository | None = None) -> None:
        self.repository = repository or ClassroomRepository()

    def health(self) -> dict[str, Any]:
        scanner = IntegrityScanner(classroom_repository=self.repository)
        orphan_scan = scanner.scan()
        with connect_sqlite(self.repository.db_path) as connection:
            duplicate_rows = connection.execute(
                """
                select assignment_id, student_id, result_id, count(*) as total
                from classroom_submissions
                group by assignment_id, student_id, result_id
                having total > 1
                """
            ).fetchall()
            analytics = self.repository.analytics()
        invalid_transitions: list[str] = []
        if analytics["assignments_completed"] > analytics["assignments_started"] and analytics["assignments_started"] > 0:
            invalid_transitions.append("completed exceeds started")
        return {
            "status": "INTEGRITY_FAILED" if duplicate_rows or invalid_transitions else "INTEGRITY_OK",
            "lifecycle": analytics,
            "duplicate_events": [dict(row) for row in duplicate_rows],
            "invalid_transitions": invalid_transitions,
            "orphan_scan": orphan_scan,
        }


class PerformanceBaselineService:
    def measure(self, operations: dict[str, Callable[[], Any]], iterations: int = 3) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for name, operation in operations.items():
            durations: list[float] = []
            for _ in range(iterations):
                start = time.perf_counter()
                operation()
                durations.append((time.perf_counter() - start) * 1000)
            results[name] = self._stats(durations)
        return results

    def _stats(self, durations: list[float]) -> dict[str, float]:
        ordered = sorted(durations)
        return {
            "average_ms": round(statistics.mean(ordered), 2),
            "p95_ms": round(self._percentile(ordered, 0.95), 2),
            "p99_ms": round(self._percentile(ordered, 0.99), 2),
        }

    def _percentile(self, values: list[float], percentile: float) -> float:
        if not values:
            return 0.0
        index = min(len(values) - 1, int(round((len(values) - 1) * percentile)))
        return values[index]
