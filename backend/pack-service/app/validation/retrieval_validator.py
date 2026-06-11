from __future__ import annotations

from typing import Any


class RetrievalValidator:
    def validate(self, manifest: dict[str, Any], artifacts: dict[str, Any]) -> tuple[bool, list[str]]:
        errors: list[str] = []
        retrieval_index_version = manifest.get("retrieval_index_version")
        if not retrieval_index_version:
            errors.append("retrieval_index_version:missing")

        retrieval_index = artifacts.get("retrieval_index", {})
        if not isinstance(retrieval_index, dict):
            errors.append("retrieval_index:not-a-dict")
        elif not retrieval_index:
            errors.append("retrieval_index:empty")

        return not errors, errors
