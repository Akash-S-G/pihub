from __future__ import annotations

from typing import Any

from .migrations import ManifestCompatibilityService, ManifestMigrationService
from .models import CompatibilityResult, ExperimentTemplate, MigrationResult, ValidationResult
from .template_repository import ManifestTemplateRepository
from .validator import ExperimentManifestValidator


class ExperimentManifestService:
    def __init__(
        self,
        templates: ManifestTemplateRepository | None = None,
        validator: ExperimentManifestValidator | None = None,
        compatibility: ManifestCompatibilityService | None = None,
        migrations: ManifestMigrationService | None = None,
    ) -> None:
        self.templates = templates or ManifestTemplateRepository()
        self.validator = validator or ExperimentManifestValidator()
        self.compatibility = compatibility or ManifestCompatibilityService()
        self.migrations = migrations or ManifestMigrationService()

    def list_templates(self) -> list[ExperimentTemplate]:
        return self.templates.list_templates()

    def get_template(self, template_id: str) -> ExperimentTemplate | None:
        return self.templates.get_template(template_id)

    def validate(self, manifest: dict[str, Any]) -> ValidationResult:
        return self.validator.validate(manifest)

    def validate_execution(self, execution: dict[str, Any]) -> ValidationResult:
        return self.validator.validate_execution(execution)

    def validate_scene(self, scene: dict[str, Any]) -> ValidationResult:
        return self.validator.validate_scene(scene)

    def check_compatibility(self, manifest: dict[str, Any]) -> CompatibilityResult:
        return self.compatibility.check(manifest)

    def migrate(self, manifest: dict[str, Any]) -> MigrationResult:
        return self.migrations.migrate(manifest)
