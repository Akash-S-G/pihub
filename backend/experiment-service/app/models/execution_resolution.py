from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DeviceCapabilities(BaseModel):
    accelerometer: bool | None = None
    gyroscope: bool | None = None
    magnetometer: bool | None = None
    gps: bool | None = None
    camera: bool | None = None
    microphone: bool | None = None
    barometer: bool | None = None
    light_sensor: bool | None = None
    storage: bool | None = None
    network: bool | None = None

    class Config:
        extra = "allow"


class ExecutionResolutionRequest(BaseModel):
    manifest_id: str
    device_capabilities: DeviceCapabilities = Field(default_factory=DeviceCapabilities)


class CapabilityCheckResponse(BaseModel):
    coverage: float
    available: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    recommended_mode: str | None = None


class ExecutionResolutionResponse(BaseModel):
    supported: bool
    resolved_mode: str | None = None
    coverage: float
    missing_capabilities: list[str] = Field(default_factory=list)
    reason: str
    execution_definition: dict[str, Any] | None = None
