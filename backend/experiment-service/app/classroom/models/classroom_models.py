from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.sharing.models import SharePackage


class ClassroomSession(BaseModel):
    session_id: str
    teacher_id: str
    title: str
    active: bool = True
    created_at: str


class CreateSessionRequest(BaseModel):
    teacher_id: str
    title: str
    active: bool = True


class ClassroomAssignment(BaseModel):
    assignment_id: str
    session_id: str
    manifest_id: str
    revision: int
    title: str
    instructions: str = ""
    due_date: str | None = None
    share_package: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class CreateAssignmentRequest(BaseModel):
    manifest_id: str
    revision: int | None = None
    title: str
    instructions: str = ""
    due_date: str | None = None
    source_node: str = ""


class ClassroomSubmission(BaseModel):
    submission_id: str
    assignment_id: str
    student_id: str
    result_id: str
    submitted_at: str
    verified: bool = False
    verification: dict[str, Any] = Field(default_factory=dict)


class SubmitAssignmentRequest(BaseModel):
    student_id: str
    result_id: str
    submission_package: SharePackage | None = None


class ClassroomAnalytics(BaseModel):
    assignments_created: int = 0
    assignments_started: int = 0
    assignments_completed: int = 0
    assignments_submitted: int = 0
