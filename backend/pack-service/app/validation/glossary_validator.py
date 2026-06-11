from __future__ import annotations

from typing import Any


class GlossaryValidator:
    def validate(self, glossary: list[dict[str, Any]]) -> tuple[bool, list[str]]:
        errors: list[str] = []
        seen_terms: set[str] = set()
        if not isinstance(glossary, list):
            return False, ["glossary:not-a-list"]

        for index, entry in enumerate(glossary):
            term = str(entry.get("term", "")).strip()
            definition = str(entry.get("definition", "")).strip()
            if not term:
                errors.append(f"glossary[{index}]:term-missing")
            if not definition:
                errors.append(f"glossary[{index}]:definition-missing")
            if term:
                normalized = term.lower()
                if normalized in seen_terms:
                    errors.append(f"glossary[{index}]:duplicate-term")
                seen_terms.add(normalized)

        return not errors, errors
