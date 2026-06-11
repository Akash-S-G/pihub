"""Curriculum precompilation validation pipeline."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ValidationStatus(str, Enum):
    """Validation status values."""

    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"


@dataclass
class ValidationResult:
    """Result of a single validation check."""

    check_name: str
    status: ValidationStatus
    message: str
    details: Optional[Dict] = None


class CurriculumValidationPipeline:
    """Validate curriculum compilation before distribution."""

    def __init__(self):
        """Initialize validation pipeline."""
        self.results: List[ValidationResult] = []
        self.validation_report: Dict = {
            "timestamp": None,
            "total_checks": 0,
            "passed": 0,
            "warnings": 0,
            "failed": 0,
            "success_rate": 0.0,
            "checks": [],
        }

    def validate_manifest(self, manifest_path: Path) -> Tuple[bool, List[ValidationResult]]:
        """
        Validate curriculum manifest structure and content.

        Args:
            manifest_path: Path to curriculum manifest

        Returns:
            Tuple of (is_valid, results)
        """
        self.results = []

        if not manifest_path.exists():
            self._add_result("manifest_exists", ValidationStatus.FAILED, "Manifest file not found")
            return False, self.results

        try:
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
        except Exception as e:
            self._add_result("manifest_parseable", ValidationStatus.FAILED, f"Failed to parse manifest: {e}")
            return False, self.results

        # Check manifest structure
        self._validate_manifest_structure(manifest)

        # Check manifest completeness
        self._validate_manifest_completeness(manifest)

        # Check for duplicates
        self._check_for_duplicates(manifest)

        # Check metadata integrity
        self._validate_metadata(manifest)

        # Determine overall validity
        has_failures = any(r.status == ValidationStatus.FAILED for r in self.results)

        return not has_failures, self.results

    def validate_pack_registry(self, registry_path: Path) -> Tuple[bool, List[ValidationResult]]:
        """
        Validate pack registry structure.

        Args:
            registry_path: Path to pack registry

        Returns:
            Tuple of (is_valid, results)
        """
        self.results = []

        if not registry_path.exists():
            self._add_result("registry_exists", ValidationStatus.FAILED, "Registry file not found")
            return False, self.results

        try:
            with open(registry_path, "r") as f:
                registry = json.load(f)
        except Exception as e:
            self._add_result("registry_parseable", ValidationStatus.FAILED, f"Failed to parse registry: {e}")
            return False, self.results

        # Check registry structure
        self._validate_registry_structure(registry)

        # Check pack entries
        self._validate_pack_entries(registry)

        # Check index consistency
        self._validate_index_consistency(registry)

        has_failures = any(r.status == ValidationStatus.FAILED for r in self.results)

        return not has_failures, self.results

    def validate_enrichment_registry(self, registry_path: Path) -> Tuple[bool, List[ValidationResult]]:
        """
        Validate enrichment registry.

        Args:
            registry_path: Path to enrichment registry

        Returns:
            Tuple of (is_valid, results)
        """
        self.results = []

        if not registry_path.exists():
            self._add_result("enrichment_exists", ValidationStatus.FAILED, "Enrichment registry not found")
            return False, self.results

        try:
            with open(registry_path, "r") as f:
                registry = json.load(f)
        except Exception as e:
            self._add_result(
                "enrichment_parseable",
                ValidationStatus.FAILED,
                f"Failed to parse enrichment registry: {e}",
            )
            return False, self.results

        # Check registry structure
        required_keys = ["metadata", "simulations", "experiments", "videos", "virtual_labs", "animations"]

        for key in required_keys:
            if key not in registry:
                self._add_result(
                    f"enrichment_has_{key}",
                    ValidationStatus.WARNING,
                    f"Missing key: {key}",
                )

        # Check metadata
        if "metadata" in registry:
            meta = registry["metadata"]
            required_meta_keys = ["version", "created_at", "total_mappings"]

            for key in required_meta_keys:
                if key not in meta:
                    self._add_result(
                        f"enrichment_meta_{key}",
                        ValidationStatus.WARNING,
                        f"Missing metadata field: {key}",
                    )

        # Check concept mappings
        if "concept_mappings" in registry:
            if not registry["concept_mappings"]:
                self._add_result(
                    "enrichment_mappings_exist",
                    ValidationStatus.WARNING,
                    "No concept mappings found",
                )

        has_failures = any(r.status == ValidationStatus.FAILED for r in self.results)

        return not has_failures, self.results

    def _validate_manifest_structure(self, manifest: Dict) -> None:
        """Validate manifest has required top-level structure."""
        required_keys = ["metadata", "curriculum_index", "curriculum_graph"]

        for key in required_keys:
            if key in manifest:
                self._add_result(
                    f"has_{key}",
                    ValidationStatus.PASSED,
                    f"Manifest has '{key}' section",
                )
            else:
                self._add_result(
                    f"has_{key}",
                    ValidationStatus.FAILED,
                    f"Missing required section: {key}",
                )

    def _validate_manifest_completeness(self, manifest: Dict) -> None:
        """Validate manifest content is complete."""
        if "curriculum_index" in manifest:
            curriculum_count = len(manifest["curriculum_index"])

            if curriculum_count > 0:
                self._add_result(
                    "curriculum_entries_exist",
                    ValidationStatus.PASSED,
                    f"Manifest contains {curriculum_count} curriculum entries",
                )
            else:
                self._add_result(
                    "curriculum_entries_exist",
                    ValidationStatus.FAILED,
                    "Manifest has empty curriculum_index",
                )

            # Sample check: verify first few entries have required fields
            required_entry_fields = ["grade", "subject", "language", "chapters"]
            sample_entries = list(manifest["curriculum_index"].items())[:3]

            for key, entry in sample_entries:
                for field in required_entry_fields:
                    if field not in entry:
                        self._add_result(
                            f"entry_has_{field}",
                            ValidationStatus.WARNING,
                            f"Entry {key} missing '{field}'",
                        )

    def _check_for_duplicates(self, manifest: Dict) -> None:
        """Check for duplicate entries."""
        if "curriculum_index" not in manifest:
            return

        # Check for duplicate chapter IDs
        chapter_ids = []

        for curriculum in manifest["curriculum_index"].values():
            for chapter in curriculum.get("chapters", []):
                chapter_id = chapter.get("chapter_id")

                if chapter_id in chapter_ids:
                    self._add_result(
                        "unique_chapter_ids",
                        ValidationStatus.WARNING,
                        f"Duplicate chapter ID found: {chapter_id}",
                    )
                else:
                    chapter_ids.append(chapter_id)

        if len(chapter_ids) > 0 and len(chapter_ids) == len(set(chapter_ids)):
            self._add_result(
                "unique_chapter_ids",
                ValidationStatus.PASSED,
                f"All {len(chapter_ids)} chapter IDs are unique",
            )

    def _validate_metadata(self, manifest: Dict) -> None:
        """Validate manifest metadata."""
        if "metadata" not in manifest:
            self._add_result("has_metadata", ValidationStatus.FAILED, "Missing metadata section")
            return

        meta = manifest["metadata"]

        required_meta_fields = ["version", "created_at", "total_chapters"]

        for field in required_meta_fields:
            if field in meta:
                self._add_result(
                    f"meta_{field}",
                    ValidationStatus.PASSED,
                    f"Metadata contains '{field}': {meta[field]}",
                )
            else:
                self._add_result(
                    f"meta_{field}",
                    ValidationStatus.WARNING,
                    f"Missing metadata field: {field}",
                )

    def _validate_registry_structure(self, registry: Dict) -> None:
        """Validate pack registry structure."""
        required_keys = ["metadata", "packs", "index"]

        for key in required_keys:
            if key in registry:
                self._add_result(
                    f"has_{key}",
                    ValidationStatus.PASSED,
                    f"Registry has '{key}' section",
                )
            else:
                self._add_result(
                    f"has_{key}",
                    ValidationStatus.FAILED,
                    f"Missing required section: {key}",
                )

    def _validate_pack_entries(self, registry: Dict) -> None:
        """Validate pack entries in registry."""
        if "packs" not in registry:
            return

        packs = registry["packs"]
        pack_count = len(packs)

        if pack_count > 0:
            self._add_result(
                "has_packs",
                ValidationStatus.PASSED,
                f"Registry contains {pack_count} pack entries",
            )

            # Sample validation
            required_pack_fields = ["pack_id", "grade", "subject", "chapter", "language"]
            sample_packs = list(packs.items())[:3]

            for pack_id, pack_entry in sample_packs:
                for field in required_pack_fields:
                    if field not in pack_entry:
                        self._add_result(
                            f"pack_has_{field}",
                            ValidationStatus.WARNING,
                            f"Pack {pack_id} missing '{field}'",
                        )
        else:
            self._add_result("has_packs", ValidationStatus.WARNING, "Registry has no pack entries")

    def _validate_index_consistency(self, registry: Dict) -> None:
        """Validate index consistency."""
        if "index" not in registry or "packs" not in registry:
            return

        index = registry["index"]
        packs = registry["packs"]

        # Check all indexed packs exist
        for grade, pack_ids in index.get("by_grade", {}).items():
            for pack_id in pack_ids:
                if pack_id not in packs:
                    self._add_result(
                        "index_consistency",
                        ValidationStatus.WARNING,
                        f"Index references non-existent pack: {pack_id}",
                    )

    def _add_result(self, check_name: str, status: ValidationStatus, message: str) -> None:
        """Add validation result."""
        result = ValidationResult(check_name=check_name, status=status, message=message)
        self.results.append(result)

    def generate_report(self) -> Dict:
        """
        Generate validation report.

        Returns:
            Validation report
        """
        self.validation_report["timestamp"] = datetime.utcnow().isoformat()
        self.validation_report["total_checks"] = len(self.results)
        self.validation_report["passed"] = sum(1 for r in self.results if r.status == ValidationStatus.PASSED)
        self.validation_report["warnings"] = sum(1 for r in self.results if r.status == ValidationStatus.WARNING)
        self.validation_report["failed"] = sum(1 for r in self.results if r.status == ValidationStatus.FAILED)

        if self.validation_report["total_checks"] > 0:
            self.validation_report["success_rate"] = (
                self.validation_report["passed"] / self.validation_report["total_checks"]
            ) * 100

        self.validation_report["checks"] = [
            {
                "name": r.check_name,
                "status": r.status.value,
                "message": r.message,
            }
            for r in self.results
        ]

        return self.validation_report

    def save_report(self, output_path: Path) -> None:
        """
        Save validation report to JSON.

        Args:
            output_path: Path to save report
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(self.generate_report(), f, indent=2)

        logger.info(f"Validation report saved to {output_path}")

    def print_report(self) -> None:
        """Print validation report summary."""
        report = self.generate_report()

        print("\n" + "=" * 60)
        print("CURRICULUM VALIDATION REPORT")
        print("=" * 60)
        print(f"Total Checks: {report['total_checks']}")
        print(f"Passed: {report['passed']}")
        print(f"Warnings: {report['warnings']}")
        print(f"Failed: {report['failed']}")
        print(f"Success Rate: {report['success_rate']:.1f}%")
        print("=" * 60)

        if report["failed"] > 0:
            print("\nFAILURES:")
            for check in report["checks"]:
                if check["status"] == "failed":
                    print(f"  ✗ {check['name']}: {check['message']}")

        if report["warnings"] > 0:
            print("\nWARNINGS:")
            for check in report["checks"]:
                if check["status"] == "warning":
                    print(f"  ⚠ {check['name']}: {check['message']}")

        print("\nPASSED:")
        for check in report["checks"]:
            if check["status"] == "passed":
                print(f"  ✓ {check['name']}")

        print("\n" + "=" * 60)
