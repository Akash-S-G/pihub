from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.execution_resolution import DeviceCapabilities


class ExecutionPackageRequest(BaseModel):
    manifest_id: str
    revision: int | None = None
    device_capabilities: DeviceCapabilities = Field(default_factory=DeviceCapabilities)


class ExecutionPackageResponse(BaseModel):
    manifest_id: str
    manifest_version: str
    supported: bool
    execution_mode: str | None = None
    coverage: float
    missing_capabilities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    scene: dict[str, Any] = Field(default_factory=dict)
    variables: list[dict[str, Any]] = Field(default_factory=list)
    objects: list[dict[str, Any]] = Field(default_factory=list)
    rules: list[dict[str, Any]] = Field(default_factory=list)
