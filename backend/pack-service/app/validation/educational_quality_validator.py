from __future__ import annotations

from typing import Any


class EducationalQualityValidator:
    def validate_scores(self, scores: dict[str, float]) -> tuple[bool, list[str]]:
        errors: list[str] = []
        for key, value in scores.items():
            if not isinstance(value, (int, float)):
                errors.append(f"score:{key}:not-numeric")
            elif value < 0.0 or value > 1.0:
                errors.append(f"score:{key}:out-of-range")
        return not errors, errors

    def validate_completeness(self, manifest: dict[str, Any], artifacts: dict[str, Any]) -> tuple[bool, list[str]]:
        errors: list[str] = []
        required_artifacts = ("content", "glossary", "quizzes", "flashcards", "summaries", "enrichment")
        for key in required_artifacts:
            if key not in artifacts:
                errors.append(f"artifact:{key}:missing")
        if not manifest.get("pack_id"):
            errors.append("manifest:pack_id-missing")
        if not manifest.get("checksum"):
            errors.append("manifest:checksum-missing")
        return not errors, errors
