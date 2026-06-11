from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class DeviceRegisterRequest(BaseModel):
    device_name: str
    role: Literal["student", "teacher", "admin"] = "student"
    classroom: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeviceResponse(BaseModel):
    device_id: str
    device_name: str
    role: str
    status: str
    auth_token: str
    classroom: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClassroomUpdateRequest(BaseModel):
    classroom_name: str | None = None
    teacher_name: str | None = None
    sync_mode: Literal["offline", "hybrid", "online"] = "offline"
    metadata: dict[str, Any] = Field(default_factory=dict)


class PackCreateRequest(BaseModel):
    pack_name: str
    version: str
    subject: str | None = None
    grade: int | None = None
    chapter: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SyncRequest(BaseModel):
    action: Literal["start", "advance", "complete", "retry", "status"]
    session_id: str | None = None
    device_id: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    total_bytes: int | None = None
    bytes_transferred: int | None = None
    checksum: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProgressRequest(BaseModel):
    student_id: str
    grade: int
    subject: str
    chapter: str | None = None
    score: int = Field(ge=0, le=100)
    attempts: int = Field(ge=0)
    updated_at: str
    topic: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class QuizSessionCreateRequest(BaseModel):
    student_id: str
    active_quiz_id: str
    grade: int | None = None
    subject: str | None = None
    chapter: str | None = None
    topic: str | None = None
    current_question: int = Field(default=0, ge=0)
    score: int = Field(default=0, ge=0)
    total_questions: int | None = Field(default=None, ge=0)
    questions: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class QuizAnswerRequest(BaseModel):
    answer: Any | None = None
    correct: bool | None = None
    score_delta: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str
    service: str
    checks: dict[str, Any] = Field(default_factory=dict)
