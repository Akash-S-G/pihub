from __future__ import annotations

import logging

from analytics.analytics_models import ExperimentStats, StudentExperimentStats, SystemExperimentStats, TopExperiment
from analytics.analytics_repository import AnalyticsRepository
from app.core.observability import operation_span


logger = logging.getLogger("experiment-service.analytics")


class ExperimentAnalyticsService:
    def __init__(self, repository: AnalyticsRepository | None = None) -> None:
        self.repository = repository or AnalyticsRepository()

    def student_analytics(self, student_id: str) -> StudentExperimentStats:
        logger.info("[EXPERIMENT] STUDENT_ANALYTICS_REQUEST student_id=%s", student_id)
        try:
            with operation_span("analytics_student"):
                return self.repository.get_student_stats(student_id)
        except Exception as exc:
            logger.exception("[EXPERIMENT] ANALYTICS_ERROR reason=%s", exc)
            raise

    def experiment_analytics(self, experiment_id: str) -> ExperimentStats:
        logger.info("[EXPERIMENT] EXPERIMENT_ANALYTICS_REQUEST experiment_id=%s", experiment_id)
        try:
            with operation_span("analytics_experiment", manifest_id=experiment_id):
                return self.repository.get_experiment_stats(experiment_id)
        except Exception as exc:
            logger.exception("[EXPERIMENT] ANALYTICS_ERROR reason=%s", exc)
            raise

    def system_analytics(self) -> SystemExperimentStats:
        logger.info("[EXPERIMENT] SYSTEM_ANALYTICS_REQUEST")
        try:
            with operation_span("analytics_system"):
                return self.repository.get_system_stats()
        except Exception as exc:
            logger.exception("[EXPERIMENT] ANALYTICS_ERROR reason=%s", exc)
            raise

    def top_experiments(self, limit: int = 10) -> list[TopExperiment]:
        logger.info("[EXPERIMENT] TOP_EXPERIMENTS_REQUEST limit=%s", limit)
        try:
            with operation_span("analytics_top_experiments"):
                return self.repository.get_top_experiments(limit)
        except Exception as exc:
            logger.exception("[EXPERIMENT] ANALYTICS_ERROR reason=%s", exc)
            raise

    def metrics(self) -> dict[str, int]:
        logger.info("[EXPERIMENT] METRICS_REQUEST")
        try:
            with operation_span("analytics_metrics"):
                return self.repository.metrics()
        except Exception as exc:
            logger.exception("[EXPERIMENT] ANALYTICS_ERROR reason=%s", exc)
            raise
