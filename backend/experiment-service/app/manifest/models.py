from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


CURRENT_MANIFEST_VERSION = "1.0.0"


class TemplateCategory(StrEnum):
    PHYSICS = "Physics"
    CHEMISTRY = "Chemistry"
    BIOLOGY = "Biology"
    MATHEMATICS = "Mathematics"
    GEOGRAPHY = "Geography"
    ENVIRONMENTAL_SCIENCE = "EnvironmentalScience"
    CUSTOM = "Custom"


class ValidationResult(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    manifest_version: str | None = None


class ManifestVariable(BaseModel):
    name: str
    type: str
    default_value: Any | None = None
    min_value: float | None = None
    max_value: float | None = None
    unit: str | None = None
    description: str | None = None


class ManifestObject(BaseModel):
    object_id: str
    object_type: str
    name: str
    properties: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ManifestRule(BaseModel):
    rule_id: str
    name: str
    trigger: str
    condition: dict[str, Any] = Field(default_factory=dict)
    action: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class ManifestScene(BaseModel):
    scene_id: str
    name: str
    description: str | None = None
    objects: list[ManifestObject] = Field(default_factory=list)
    variables: list[ManifestVariable] = Field(default_factory=list)
    rules: list[ManifestRule] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ManifestExecutionDefinition(BaseModel):
    supported_modes: list[str] = Field(default_factory=list)
    required_sensors: list[str] = Field(default_factory=list)
    scene: ManifestScene
    variables: list[ManifestVariable] = Field(default_factory=list)
    objects: list[ManifestObject] = Field(default_factory=list)
    rules: list[ManifestRule] = Field(default_factory=list)


class CompatibilityResult(BaseModel):
    compatible: bool
    manifest_version: str | None = None
    current_version: str = CURRENT_MANIFEST_VERSION
    deprecated_fields: list[str] = Field(default_factory=list)
    migration_recommendations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class MigrationResult(BaseModel):
    migrated: bool
    from_version: str | None = None
    to_version: str = CURRENT_MANIFEST_VERSION
    manifest: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


class ExperimentTemplate(BaseModel):
    template_id: str
    template_name: str
    category: TemplateCategory
    manifest: dict[str, Any]
    description: str
    version: str = CURRENT_MANIFEST_VERSION
