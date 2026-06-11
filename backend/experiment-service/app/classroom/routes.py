from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder

from app.core.pagination import page_query, page_size_query, paginate
from app.classroom.models import CreateAssignmentRequest, CreateSessionRequest, SubmitAssignmentRequest
from app.classroom.services.classroom_service import ClassroomNotFoundError, ClassroomService, ClassroomValidationError


router = APIRouter(tags=["Classroom Distribution"])
classroom_service = ClassroomService()


def _dump(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    if hasattr(model, "dict"):
        return jsonable_encoder(model.dict())
    return jsonable_encoder(dict(model))


def _parse_model(model_type: Any, payload: dict[str, Any]) -> Any:
    if hasattr(model_type, "model_validate"):
        return model_type.model_validate(payload)
    return model_type.parse_obj(payload)


@router.post("/classroom/sessions")
async def create_classroom_session(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        request = _parse_model(CreateSessionRequest, payload)
        return _dump(classroom_service.create_session(request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/classroom/sessions")
async def list_classroom_sessions(page: int = page_query(), page_size: int = page_size_query()) -> dict[str, Any]:
    sessions = classroom_service.list_sessions()
    paged = paginate(sessions, page, page_size)
    return {
        "sessions": [_dump(session) for session in paged["items"]],
        "page": page,
        "page_size": page_size,
        "total": paged["total"],
    }


@router.post("/classroom/sessions/{session_id}/assignments")
async def create_classroom_assignment(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        request = _parse_model(CreateAssignmentRequest, payload)
        return _dump(classroom_service.create_assignment(session_id, request))
    except ClassroomNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ClassroomValidationError as exc:
        raise HTTPException(status_code=400, detail={"errors": exc.errors}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/classroom/sessions/{session_id}/assignments")
async def list_classroom_assignments(
    session_id: str,
    page: int = page_query(),
    page_size: int = page_size_query(),
) -> dict[str, Any]:
    try:
        assignments = classroom_service.list_assignments(session_id)
    except ClassroomNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    paged = paginate(assignments, page, page_size)
    return {"assignments": [_dump(assignment) for assignment in paged["items"]], "page": page, "page_size": page_size, "total": paged["total"]}


@router.post("/classroom/assignments/{assignment_id}/submit")
async def submit_classroom_assignment(assignment_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        request = _parse_model(SubmitAssignmentRequest, payload)
        return _dump(classroom_service.submit_assignment(assignment_id, request))
    except ClassroomNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ClassroomValidationError as exc:
        raise HTTPException(status_code=400, detail={"errors": exc.errors}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/classroom/assignments/{assignment_id}/submissions")
async def list_classroom_submissions(
    assignment_id: str,
    page: int = page_query(),
    page_size: int = page_size_query(),
) -> dict[str, Any]:
    try:
        submissions = classroom_service.list_submissions(assignment_id)
    except ClassroomNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    paged = paginate(submissions, page, page_size)
    return {"submissions": [_dump(submission) for submission in paged["items"]], "page": page, "page_size": page_size, "total": paged["total"]}


@router.get("/classroom/analytics")
async def classroom_analytics() -> dict[str, Any]:
    return _dump(classroom_service.analytics())
