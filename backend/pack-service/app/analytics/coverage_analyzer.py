from __future__ import annotations

from collections import defaultdict
from typing import Any


class PackCoverageAnalyzer:
    REQUIRED_ARTIFACTS = ("content", "summaries", "glossary", "quizzes", "flashcards")

    def analyze(self, packs: list[dict[str, Any]]) -> dict[str, Any]:
        groups: dict[str, dict[str, Any]] = {}
        missing_artifacts: list[dict[str, Any]] = []
        complete = 0
        artifact_presence = defaultdict(int)

        for pack in packs:
            counts = pack.get("artifact_counts") or {}
            missing = [name for name in self.REQUIRED_ARTIFACTS if int(counts.get(name) or 0) <= 0]
            if missing:
                missing_artifacts.append({
                    "pack_id": pack.get("pack_id"),
                    "grade": pack.get("grade"),
                    "subject": pack.get("subject"),
                    "chapter": pack.get("chapter"),
                    "missing": missing,
                })
            else:
                complete += 1

            for name in self.REQUIRED_ARTIFACTS:
                if int(counts.get(name) or 0) > 0:
                    artifact_presence[name] += 1

            group_key = f"{pack.get('grade') or 'unknown'}::{pack.get('subject') or 'unknown'}"
            group = groups.setdefault(
                group_key,
                {
                    "grade": pack.get("grade"),
                    "subject": pack.get("subject") or "unknown",
                    "chapters_total": 0,
                    "chapters_complete": 0,
                    "summaries": 0,
                    "glossary": 0,
                    "mcqs": 0,
                    "flashcards": 0,
                    "missing_artifacts": [],
                },
            )
            group["chapters_total"] += 1
            if not missing:
                group["chapters_complete"] += 1
            if int(counts.get("summaries") or 0) > 0:
                group["summaries"] += 1
            if int(counts.get("glossary") or 0) > 0:
                group["glossary"] += 1
            if int(counts.get("quizzes") or 0) > 0:
                group["mcqs"] += 1
            if int(counts.get("flashcards") or 0) > 0:
                group["flashcards"] += 1
            if missing:
                group["missing_artifacts"].append({"pack_id": pack.get("pack_id"), "missing": missing})

        by_grade_subject = sorted(
            groups.values(),
            key=lambda item: (int(item["grade"] or 0), str(item["subject"])),
        )

        return {
            "chapters_total": len(packs),
            "chapters_complete": complete,
            "completion_percent": round((complete / len(packs)) * 100, 2) if packs else 0.0,
            "summaries": artifact_presence["summaries"],
            "glossary": artifact_presence["glossary"],
            "mcqs": artifact_presence["quizzes"],
            "flashcards": artifact_presence["flashcards"],
            "missing_artifacts": missing_artifacts,
            "by_grade_subject": by_grade_subject,
        }
