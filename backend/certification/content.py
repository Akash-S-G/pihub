from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from .client import APIClient


@dataclass
class ContentCompletenessAuditor:
    client: APIClient

    def run(self) -> dict[str, Any]:
        coverage = self.client.get_json("/packs/coverage")
        packs = self.client.get_json("/packs").get("packs", [])
        by_grade: dict[str, dict[str, Any]] = defaultdict(lambda: {
            "grade": None,
            "chapters_total": 0,
            "chapters_complete": 0,
            "summaries": 0,
            "glossary": 0,
            "mcqs": 0,
            "flashcards": 0,
            "missing_artifacts": [],
        })
        artifact_totals: Counter[str] = Counter()
        complete_packs = 0

        for item in packs:
            grade = str(item.get("grade") or "unknown")
            bucket = by_grade[grade]
            bucket["grade"] = item.get("grade")
            bucket["chapters_total"] += 1
            counts = item.get("artifact_counts") or {}
            missing = [name for name in ("content", "summaries", "glossary", "quizzes", "flashcards") if int(counts.get(name) or 0) <= 0]
            if not missing:
                bucket["chapters_complete"] += 1
                complete_packs += 1
            else:
                bucket["missing_artifacts"].append({
                    "pack_id": item.get("pack_id"),
                    "subject": item.get("subject"),
                    "chapter": item.get("chapter"),
                    "missing": missing,
                })
            bucket["summaries"] += 1 if int(counts.get("summaries") or 0) > 0 else 0
            bucket["glossary"] += 1 if int(counts.get("glossary") or 0) > 0 else 0
            bucket["mcqs"] += 1 if int(counts.get("quizzes") or 0) > 0 else 0
            bucket["flashcards"] += 1 if int(counts.get("flashcards") or 0) > 0 else 0
            for artifact_name in ("content", "summaries", "glossary", "quizzes", "flashcards"):
                artifact_totals[artifact_name] += 1 if int(counts.get(artifact_name) or 0) > 0 else 0

        summary = {
            "total_packs": len(packs),
            "complete_packs": complete_packs,
            "completion_percent": round((complete_packs / len(packs)) * 100, 2) if packs else 0.0,
            "artifact_totals": dict(artifact_totals),
            "coverage": coverage,
            "by_grade": [by_grade[key] for key in sorted(by_grade, key=lambda value: int(value) if value.isdigit() else 999)],
        }
        return summary

    @staticmethod
    def to_markdown(report: dict[str, Any]) -> str:
        lines = [
            "# Content Completeness Report",
            "",
            f"Total packs: {report['total_packs']}",
            f"Complete packs: {report['complete_packs']}",
            f"Completion percent: {report['completion_percent']:.2f}%",
            "",
            "## Artifacts",
        ]
        for key, value in sorted(report["artifact_totals"].items()):
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Grade Summary"])
        for grade in report["by_grade"]:
            lines.append(
                f"- Grade {grade['grade']}: {grade['chapters_complete']}/{grade['chapters_total']} complete, "
                f"summaries={grade['summaries']}, glossary={grade['glossary']}, mcqs={grade['mcqs']}, flashcards={grade['flashcards']}"
            )
            if grade["missing_artifacts"]:
                lines.append(f"  Missing examples: {grade['missing_artifacts'][:3]}")
        lines.extend(["", "## Verdict", "", "PASS" if report["completion_percent"] >= 95.0 else "REQUIRES_ADDITIONAL_WORK", ""])
        return "\n".join(lines)
