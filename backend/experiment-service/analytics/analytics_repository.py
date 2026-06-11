from __future__ import annotations

import sqlite3

from analytics.analytics_models import ExperimentStats, StudentExperimentStats, SystemExperimentStats, TopExperiment
from repositories.sqlite_run_repository import ExperimentSqliteStore


ACTIVE_STATUSES = ("created", "running", "paused")


def _round_or_none(value: object) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


class AnalyticsRepository:
    def __init__(self, store: ExperimentSqliteStore | None = None) -> None:
        self.store = store or ExperimentSqliteStore()

    def get_student_stats(self, student_id: str) -> StudentExperimentStats:
        with self.store.connect() as connection:
            row = connection.execute(
                """
                select
                    count(r.run_id) as total_runs,
                    sum(case when r.status = 'completed' then 1 else 0 end) as completed_runs,
                    sum(case when r.status = 'failed' then 1 else 0 end) as failed_runs,
                    sum(case when r.status in ('created', 'running', 'paused') then 1 else 0 end) as active_runs,
                    avg(res.score) as average_score,
                    avg(res.completion_percentage) as average_completion,
                    avg(r.duration_ms) as average_duration_ms,
                    coalesce(sum(r.duration_ms), 0) as total_time_spent_ms
                from experiment_runs r
                left join experiment_results res on res.run_id = r.run_id
                where r.student_id = ?
                """,
                (student_id,),
            ).fetchone()
        return StudentExperimentStats(
            student_id=student_id,
            total_runs=int(row["total_runs"] or 0),
            completed_runs=int(row["completed_runs"] or 0),
            failed_runs=int(row["failed_runs"] or 0),
            active_runs=int(row["active_runs"] or 0),
            average_score=_round_or_none(row["average_score"]),
            average_completion=_round_or_none(row["average_completion"]),
            average_duration_ms=_round_or_none(row["average_duration_ms"]),
            total_time_spent_ms=int(row["total_time_spent_ms"] or 0),
        )

    def get_experiment_stats(self, experiment_id: str) -> ExperimentStats:
        with self.store.connect() as connection:
            row = connection.execute(
                """
                select
                    count(r.run_id) as total_runs,
                    sum(case when r.status = 'completed' then 1 else 0 end) as completed_runs,
                    sum(case when r.status = 'failed' then 1 else 0 end) as failed_runs,
                    avg(res.score) as average_score,
                    avg(res.completion_percentage) as average_completion,
                    avg(r.duration_ms) as average_duration_ms,
                    count(distinct r.student_id) as unique_students
                from experiment_runs r
                left join experiment_results res on res.run_id = r.run_id
                where r.experiment_id = ?
                """,
                (experiment_id,),
            ).fetchone()
        return ExperimentStats(
            experiment_id=experiment_id,
            total_runs=int(row["total_runs"] or 0),
            completed_runs=int(row["completed_runs"] or 0),
            failed_runs=int(row["failed_runs"] or 0),
            average_score=_round_or_none(row["average_score"]),
            average_completion=_round_or_none(row["average_completion"]),
            average_duration_ms=_round_or_none(row["average_duration_ms"]),
            unique_students=int(row["unique_students"] or 0),
        )

    def get_system_stats(self) -> SystemExperimentStats:
        with self.store.connect() as connection:
            run_row = connection.execute(
                """
                select
                    count(r.run_id) as total_runs,
                    sum(case when r.status = 'completed' then 1 else 0 end) as completed_runs,
                    sum(case when r.status = 'failed' then 1 else 0 end) as failed_runs,
                    sum(case when r.status in ('created', 'running', 'paused') then 1 else 0 end) as active_runs,
                    count(distinct r.student_id) as total_students,
                    count(distinct r.experiment_id) as total_experiments,
                    avg(res.score) as average_score,
                    avg(res.completion_percentage) as average_completion,
                    avg(r.duration_ms) as average_duration_ms
                from experiment_runs r
                left join experiment_results res on res.run_id = r.run_id
                """
            ).fetchone()
            event_row = connection.execute("select count(*) as total_events from experiment_run_events").fetchone()
            result_row = connection.execute("select count(*) as total_results from experiment_results").fetchone()
        return SystemExperimentStats(
            total_runs=int(run_row["total_runs"] or 0),
            completed_runs=int(run_row["completed_runs"] or 0),
            failed_runs=int(run_row["failed_runs"] or 0),
            active_runs=int(run_row["active_runs"] or 0),
            total_students=int(run_row["total_students"] or 0),
            total_experiments=int(run_row["total_experiments"] or 0),
            average_score=_round_or_none(run_row["average_score"]),
            average_completion=_round_or_none(run_row["average_completion"]),
            average_duration_ms=_round_or_none(run_row["average_duration_ms"]),
            total_events=int(event_row["total_events"] or 0),
            total_results=int(result_row["total_results"] or 0),
        )

    def get_top_experiments(self, limit: int) -> list[TopExperiment]:
        bounded_limit = max(1, min(int(limit), 100))
        with self.store.connect() as connection:
            rows = connection.execute(
                """
                select
                    r.experiment_id as experiment_id,
                    count(r.run_id) as run_count,
                    avg(case when r.status = 'completed' then 1.0 else 0.0 end) * 100.0 as completion_rate,
                    avg(res.score) as average_score
                from experiment_runs r
                left join experiment_results res on res.run_id = r.run_id
                group by r.experiment_id
                order by run_count desc, completion_rate desc
                limit ?
                """,
                (bounded_limit,),
            ).fetchall()
        return [self._row_to_top(row) for row in rows]

    def metrics(self) -> dict[str, int]:
        stats = self.get_system_stats()
        return {
            "total_runs": stats.total_runs,
            "completed_runs": stats.completed_runs,
            "active_runs": stats.active_runs,
            "failed_runs": stats.failed_runs,
            "events_stored": stats.total_events,
            "results_stored": stats.total_results,
        }

    @staticmethod
    def _row_to_top(row: sqlite3.Row) -> TopExperiment:
        return TopExperiment(
            experiment_id=row["experiment_id"],
            run_count=int(row["run_count"] or 0),
            completion_rate=round(float(row["completion_rate"] or 0.0), 2),
            average_score=_round_or_none(row["average_score"]),
        )
