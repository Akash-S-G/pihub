from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.classroom.models import (
    ClassroomAnalytics,
    ClassroomAssignment,
    ClassroomSession,
    ClassroomSubmission,
    CreateAssignmentRequest,
    CreateSessionRequest,
    SubmitAssignmentRequest,
)
from app.classroom.repositories.classroom_repository import ClassroomRepository
from app.sharing.models import ShareExportRequest
from app.sharing.services.experiment_sharing_service import ExperimentSharingService, SharingNotFoundError, SharingValidationError
from app.core.observability import operation_span


logger = logging.getLogger("experiment-service.classroom")


class ClassroomNotFoundError(ValueError):
    pass


class ClassroomValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class ClassroomService:
    def __init__(
        self,
        repository: ClassroomRepository | None = None,
        sharing_service: ExperimentSharingService | None = None,
    ) -> None:
        self.repository = repository or ClassroomRepository()
        self.sharing_service = sharing_service or ExperimentSharingService()

    def create_session(self, request: CreateSessionRequest) -> ClassroomSession:
        logger.info("[CLASSROOM] SESSION_CREATE teacher_id=%s", request.teacher_id)
        record = self.repository.create_session(
            {
                "session_id": str(uuid4()),
                "teacher_id": request.teacher_id,
                "title": request.title,
                "active": request.active,
                "created_at": self._now(),
            }
        )
        return ClassroomSession(**record)

    def list_sessions(self) -> list[ClassroomSession]:
        return [ClassroomSession(**record) for record in self.repository.list_sessions()]

    def create_assignment(self, session_id: str, request: CreateAssignmentRequest) -> ClassroomAssignment:
        logger.info("[CLASSROOM] ASSIGNMENT_CREATE session_id=%s manifest_id=%s", session_id, request.manifest_id)
        with operation_span("classroom_assignment_created", manifest_id=request.manifest_id, revision=request.revision):
            session = self.repository.get_session(session_id)
            if session is None:
                raise ClassroomNotFoundError(f"Session not found: {session_id}")
            if not session["active"]:
                raise ClassroomValidationError(["Cannot create assignments in inactive sessions"])

        try:
            share_package = self.sharing_service.export_package(
                ShareExportRequest(
                    manifest_id=request.manifest_id,
                    revision=request.revision,
                    author=session["teacher_id"],
                    source_node=request.source_node,
                )
            )
        except SharingNotFoundError as exc:
            raise ClassroomNotFoundError(str(exc)) from exc
        except SharingValidationError as exc:
            raise ClassroomValidationError(exc.errors) from exc

        package_payload = self._dump(share_package)
        revision = int(package_payload.get("revision", {}).get("revision") or request.revision or 1)
        record = self.repository.create_assignment(
            {
                "assignment_id": str(uuid4()),
                "session_id": session_id,
                "manifest_id": request.manifest_id,
                "revision": revision,
                "title": request.title,
                "instructions": request.instructions,
                "due_date": request.due_date,
                "share_package": package_payload,
                "created_at": self._now(),
            }
        )
        return ClassroomAssignment(**record)

    def list_assignments(self, session_id: str) -> list[ClassroomAssignment]:
        if self.repository.get_session(session_id) is None:
            raise ClassroomNotFoundError(f"Session not found: {session_id}")
        return [ClassroomAssignment(**record) for record in self.repository.list_assignments(session_id)]

    def submit_assignment(self, assignment_id: str, request: SubmitAssignmentRequest) -> ClassroomSubmission:
        logger.info("[CLASSROOM] SUBMISSION_CREATE assignment_id=%s student_id=%s", assignment_id, request.student_id)
        with operation_span("classroom_assignment_submitted"):
            assignment = self.repository.get_assignment(assignment_id)
            if assignment is None:
                raise ClassroomNotFoundError(f"Assignment not found: {assignment_id}")

        verification: dict[str, Any] = {}
        verified = False
        if request.submission_package is not None:
            verify_result = self.sharing_service.verify_package(request.submission_package)
            verification = self._dump(verify_result)
            if not verify_result.valid:
                raise ClassroomValidationError(verify_result.errors)
            verified = True

        submitted_at = self._now()
        try:
            record = self.repository.create_submission_with_student(
                assignment["session_id"],
                {
                    "submission_id": str(uuid4()),
                    "assignment_id": assignment_id,
                    "student_id": request.student_id,
                    "result_id": request.result_id,
                    "submission_package": self._dump(request.submission_package) if request.submission_package is not None else None,
                    "verified": verified,
                    "verification": verification,
                    "submitted_at": submitted_at,
                },
                submitted_at,
            )
        except sqlite3.IntegrityError as exc:
            raise ClassroomValidationError(["Duplicate submission for assignment, student, and result"]) from exc
        return ClassroomSubmission(**record)

    def list_submissions(self, assignment_id: str) -> list[ClassroomSubmission]:
        if self.repository.get_assignment(assignment_id) is None:
            raise ClassroomNotFoundError(f"Assignment not found: {assignment_id}")
        return [ClassroomSubmission(**record) for record in self.repository.list_submissions(assignment_id)]

    def analytics(self) -> ClassroomAnalytics:
        return ClassroomAnalytics(**self.repository.analytics())

    def _dump(self, model: Any) -> dict[str, Any]:
        if hasattr(model, "model_dump"):
            return model.model_dump(mode="json")
        if hasattr(model, "dict"):
            return model.dict()
        return dict(model)

    def _now(self) -> str:
        return datetime.now(UTC).isoformat()
