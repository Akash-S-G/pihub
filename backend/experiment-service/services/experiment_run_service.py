from __future__ import annotations

import logging
import uuid

from fastapi import HTTPException

from domain.enums import ExperimentExecutionMode, ExperimentStatus
from domain.models import ExperimentResult, ExperimentRun, ExperimentRunEvent
from repositories.sqlite_run_repository import (
    ExperimentSqliteStore,
    SqliteExperimentEventRepository,
    SqliteExperimentResultRepository,
    SqliteExperimentRunRepository,
    utc_now,
)
from schemas.contracts import AppendExperimentEventRequest, CompleteExperimentRunRequest, CreateExperimentRunRequest


logger = logging.getLogger("experiment-service.runs")


VALID_TRANSITIONS: dict[ExperimentStatus, set[ExperimentStatus]] = {
    ExperimentStatus.CREATED: {ExperimentStatus.RUNNING, ExperimentStatus.FAILED, ExperimentStatus.COMPLETED},
    ExperimentStatus.RUNNING: {ExperimentStatus.PAUSED, ExperimentStatus.COMPLETED, ExperimentStatus.FAILED},
    ExperimentStatus.PAUSED: {ExperimentStatus.RUNNING, ExperimentStatus.COMPLETED, ExperimentStatus.FAILED},
    ExperimentStatus.COMPLETED: set(),
    ExperimentStatus.FAILED: set(),
    ExperimentStatus.DRAFT: {ExperimentStatus.READY, ExperimentStatus.FAILED},
    ExperimentStatus.READY: {ExperimentStatus.CREATED, ExperimentStatus.RUNNING, ExperimentStatus.FAILED},
}


class ExperimentRunService:
    def __init__(self, store: ExperimentSqliteStore | None = None) -> None:
        shared_store = store or ExperimentSqliteStore()
        self.runs = SqliteExperimentRunRepository(shared_store)
        self.events = SqliteExperimentEventRepository(shared_store)
        self.results = SqliteExperimentResultRepository(shared_store)

    async def create_run(self, request: CreateExperimentRunRequest) -> ExperimentRun:
        if not request.experiment_id:
            raise HTTPException(status_code=400, detail="experiment_id is required")
        if not request.student_id:
            raise HTTPException(status_code=400, detail="student_id is required")
        if not request.execution_mode:
            raise HTTPException(status_code=400, detail="execution_mode is required")

        run = ExperimentRun(
            run_id=str(uuid.uuid4()),
            experiment_id=request.experiment_id,
            student_id=request.student_id,
            execution_mode=ExperimentExecutionMode(request.execution_mode),
            status=ExperimentStatus.CREATED,
            started_at=None,
            completed_at=None,
            duration_ms=None,
        )
        created = await self.runs.create_run(run)
        logger.info(
            "[EXPERIMENT] RUN_CREATED run_id=%s experiment_id=%s student_id=%s execution_mode=%s",
            created.run_id,
            created.experiment_id,
            created.student_id,
            created.execution_mode,
        )
        return created

    async def load_run(self, run_id: str) -> ExperimentRun:
        run = await self.runs.get_run(run_id)
        if run is None:
            logger.error("[EXPERIMENT] RUN_NOT_FOUND run_id=%s", run_id)
            raise HTTPException(status_code=404, detail="Experiment run not found")
        logger.info("[EXPERIMENT] RUN_LOADED run_id=%s", run_id)
        return run

    async def list_student_runs(self, student_id: str) -> list[ExperimentRun]:
        return await self.runs.list_student_runs(student_id)

    async def update_run_status(self, run_id: str, status: ExperimentStatus) -> ExperimentRun:
        run = await self.load_run(run_id)
        self._validate_transition(run.status, status)
        updated = await self.runs.update_run_status(run_id, status)
        if updated is None:
            logger.error("[EXPERIMENT] RUN_NOT_FOUND run_id=%s", run_id)
            raise HTTPException(status_code=404, detail="Experiment run not found")
        return updated

    async def append_event(self, run_id: str, request: AppendExperimentEventRequest) -> ExperimentRunEvent:
        if not request.event_type:
            raise HTTPException(status_code=400, detail="event_type is required")
        await self.load_run(run_id)
        event = ExperimentRunEvent(
            event_id=str(uuid.uuid4()),
            run_id=run_id,
            event_type=request.event_type,
            timestamp=utc_now(),
            payload=request.payload,
        )
        saved = await self.events.append_event(event)
        logger.info("[EXPERIMENT] EVENT_RECEIVED run_id=%s event_type=%s", run_id, request.event_type)
        return saved

    async def get_events(self, run_id: str) -> list[ExperimentRunEvent]:
        await self.load_run(run_id)
        return await self.events.get_events(run_id)

    async def complete_run(self, run_id: str, request: CompleteExperimentRunRequest) -> ExperimentRun:
        run = await self.load_run(run_id)
        self._validate_transition(run.status, ExperimentStatus.COMPLETED)
        result = ExperimentResult(
            result_id=str(uuid.uuid4()),
            run_id=run_id,
            completion_percentage=request.completion_percentage,
            score=request.score,
            observations=request.observations,
            measurements=request.measurements,
            notes=request.notes,
        )
        await self.results.save_result(result)
        completed = await self.runs.complete_run(run_id, result)
        if completed is None:
            logger.error("[EXPERIMENT] RUN_NOT_FOUND run_id=%s", run_id)
            raise HTTPException(status_code=404, detail="Experiment run not found")
        logger.info("[EXPERIMENT] RUN_COMPLETED run_id=%s duration_ms=%s", run_id, completed.duration_ms)
        return completed

    async def get_result(self, run_id: str) -> ExperimentResult | None:
        await self.load_run(run_id)
        return await self.results.get_result(run_id)

    def _validate_transition(self, current: ExperimentStatus, target: ExperimentStatus) -> None:
        if target not in VALID_TRANSITIONS.get(current, set()):
            logger.error("[EXPERIMENT] INVALID_TRANSITION current=%s target=%s", current, target)
            raise HTTPException(status_code=409, detail=f"Invalid experiment run transition: {current} -> {target}")
