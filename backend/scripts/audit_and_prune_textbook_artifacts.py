#!/usr/bin/env python3
"""Audit and prune noisy flashcards/quizzes from textbook artifact chapters."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


NOISE_MARKERS = (
    "/square6",
    "reprint 2025-26",
    "reprint 205-6",
    "tawa/pan",
    "chapter notes",
    "important idea studied in chapter",
)


@dataclass
class ChapterReport:
    chapter_root: Path
    flashcards_before: int
    flashcards_after: int
    quizzes_before: int
    quizzes_after: int
    removed_flashcards: int
    removed_quizzes: int


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("\u00a0", " ")).strip()


def is_noisy_text(text: str) -> bool:
    value = normalize_space(text).lower()
    if not value:
        return True
    if any(marker in value for marker in NOISE_MARKERS):
        return True
    if value in {"a", "b", "c", "d"}:
        return True
    if len(value) <= 3:
        return True
    return False


def prune_flashcards(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    kept: list[dict[str, Any]] = []
    removed = 0
    seen_fronts: set[str] = set()
    for item in items:
        front = normalize_space(str(item.get("front") or item.get("question") or ""))
        back = normalize_space(str(item.get("back") or item.get("answer") or ""))
        if is_noisy_text(front) or is_noisy_text(back):
            removed += 1
            continue
        key = front.lower()
        if key in seen_fronts:
            removed += 1
            continue
        seen_fronts.add(key)
        kept.append(item)
    return kept, removed


def prune_quizzes(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    kept: list[dict[str, Any]] = []
    removed = 0
    seen_questions: set[str] = set()
    for item in items:
        question = normalize_space(str(item.get("question") or ""))
        answer = normalize_space(str(item.get("answer") or item.get("correct_answer") or ""))
        explanation = normalize_space(str(item.get("explanation") or ""))
        if is_noisy_text(question) or is_noisy_text(answer):
            removed += 1
            continue
        if any(marker in explanation.lower() for marker in NOISE_MARKERS):
            removed += 1
            continue
        key = question.lower()
        if key in seen_questions:
            removed += 1
            continue
        seen_questions.add(key)
        kept.append(item)
    return kept, removed


def chapter_roots(root: Path, min_grade: int, max_grade: int) -> list[Path]:
    chapters: list[Path] = []
    for source_path in sorted(root.rglob("source/chapter_source.json")):
        chapter_root = source_path.parent.parent
        try:
            source = load_json(source_path)
            grade = int(source.get("grade"))
        except Exception:
            continue
        if grade < min_grade or grade > max_grade:
            continue
        chapters.append(chapter_root)
    return chapters


def audit_and_prune(root: Path, sample: int, min_grade: int, max_grade: int, apply_changes: bool) -> dict[str, Any]:
    chapters = chapter_roots(root, min_grade=min_grade, max_grade=max_grade)
    chapters = chapters[:sample] if sample > 0 else chapters

    reports: list[dict[str, Any]] = []
    for chapter_root in chapters:
        artifacts_dir = chapter_root / "artifacts"
        flashcards_path = artifacts_dir / "flashcards.json"
        quizzes_path = artifacts_dir / "quizzes.json"
        if not flashcards_path.exists() or not quizzes_path.exists():
            continue
        flashcards = load_json(flashcards_path)
        quizzes = load_json(quizzes_path)
        if not isinstance(flashcards, list) or not isinstance(quizzes, list):
            continue

        pruned_flashcards, removed_flashcards = prune_flashcards(flashcards)
        pruned_quizzes, removed_quizzes = prune_quizzes(quizzes)

        if apply_changes:
            if removed_flashcards:
                write_json(flashcards_path, pruned_flashcards)
            if removed_quizzes:
                write_json(quizzes_path, pruned_quizzes)

        reports.append(
            {
                "chapter_root": str(chapter_root),
                "flashcards_before": len(flashcards),
                "flashcards_after": len(pruned_flashcards),
                "quizzes_before": len(quizzes),
                "quizzes_after": len(pruned_quizzes),
                "removed_flashcards": removed_flashcards,
                "removed_quizzes": removed_quizzes,
            }
        )

    summary = {
        "chapters_audited": len(reports),
        "flashcards_removed": sum(item["removed_flashcards"] for item in reports),
        "quizzes_removed": sum(item["removed_quizzes"] for item in reports),
        "apply_changes": apply_changes,
        "sample": sample,
        "min_grade": min_grade,
        "max_grade": max_grade,
    }
    return {"summary": summary, "chapters": reports}


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit and prune noisy textbook quiz/flashcard artifacts.")
    parser.add_argument("--root", default="textbook_artifacts")
    parser.add_argument("--sample", type=int, default=8, help="How many chapters to inspect. 0 means all.")
    parser.add_argument("--min-grade", type=int, default=6)
    parser.add_argument("--max-grade", type=int, default=10)
    parser.add_argument("--apply", action="store_true", help="Write pruned artifacts back to disk.")
    parser.add_argument("--output", default=str(Path("/tmp") / "textbook_artifacts_quality_audit.json"))
    args = parser.parse_args()

    report = audit_and_prune(Path(args.root), sample=args.sample, min_grade=args.min_grade, max_grade=args.max_grade, apply_changes=args.apply)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
