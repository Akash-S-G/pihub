#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import statistics
import tarfile
from collections import Counter
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_pack_index(storage_path: Path) -> list[dict[str, Any]]:
    data = load_json(storage_path / "pack_index.json")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and isinstance(data.get("packs"), list):
        return [item for item in data["packs"] if isinstance(item, dict)]
    return []


def archive_json(record: dict[str, Any], suffix: str) -> Any:
    archive_path = Path(str(record.get("archive_path") or ""))
    if not archive_path.exists():
        return []
    with tarfile.open(archive_path, "r:gz") as archive:
        member = next((item for item in archive.getmembers() if item.isfile() and item.name.endswith(suffix)), None)
        if member is None:
            return []
        file_obj = archive.extractfile(member)
        if file_obj is None:
            return []
        return json.loads(file_obj.read().decode("utf-8"))


def norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def duplicate_count(values: list[str]) -> int:
    counts = Counter(value for value in values if value)
    return sum(count - 1 for count in counts.values() if count > 1)


def low_info(text: str) -> bool:
    value = norm(text)
    words = re.findall(r"[a-z0-9]+", value)
    return len(value) < 40 or len(words) < 8


def analyze_pack(record: dict[str, Any]) -> dict[str, Any]:
    flashcards = archive_json(record, "/flashcards.json") or []
    quizzes = archive_json(record, "/quizzes.json") or []
    summaries = archive_json(record, "/summaries.json") or []

    flashcard_fronts = [norm(item.get("front")) for item in flashcards if isinstance(item, dict)]
    flashcard_backs = [norm(item.get("back")) for item in flashcards if isinstance(item, dict)]
    quiz_questions = [norm(item.get("question")) for item in quizzes if isinstance(item, dict)]
    quiz_answers = [norm(item.get("correct_answer") or item.get("answer")) for item in quizzes if isinstance(item, dict)]
    summary_texts = [norm(item.get("text") or item.get("summary")) for item in summaries if isinstance(item, dict)]

    issues = {
        "empty_flashcards": sum(1 for front, back in zip(flashcard_fronts, flashcard_backs) if not front or not back),
        "duplicate_flashcards": duplicate_count([f"{front}|{back}" for front, back in zip(flashcard_fronts, flashcard_backs)]),
        "low_info_flashcards": sum(1 for back in flashcard_backs if low_info(back)),
        "empty_quizzes": sum(1 for question, answer in zip(quiz_questions, quiz_answers) if not question or not answer),
        "duplicate_quizzes": duplicate_count(quiz_questions),
        "low_info_quizzes": sum(1 for question in quiz_questions if low_info(question)),
        "empty_summaries": sum(1 for text in summary_texts if not text),
        "duplicate_summaries": duplicate_count(summary_texts),
        "low_info_summaries": sum(1 for text in summary_texts if low_info(text)),
        "truncated_summaries": sum(1 for text in summary_texts if text and len(text) < 120),
    }
    issue_count = sum(issues.values())
    asset_count = len(flashcards) + len(quizzes) + len(summaries)
    quality_score = round(max(0.0, 100.0 - (issue_count / max(1, asset_count)) * 100.0), 2)
    return {
        "pack_id": record.get("pack_id"),
        "grade": record.get("grade"),
        "subject": record.get("subject"),
        "chapter": record.get("chapter"),
        "flashcard_count": len(flashcards),
        "quiz_count": len(quizzes),
        "summary_count": len(summaries),
        "asset_count": asset_count,
        "issue_count": issue_count,
        "quality_score": quality_score,
        "issues": issues,
    }


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate generated pack flashcards, quizzes, and summaries.")
    parser.add_argument("--storage-path", default="/shared/packs")
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = [analyze_pack(record) for record in load_pack_index(Path(args.storage_path))]
    rows.sort(key=lambda item: item["quality_score"])
    summary = {
        "pack_count": len(rows),
        "average_asset_quality_score": round(statistics.mean([row["quality_score"] for row in rows]), 2) if rows else 0,
        "total_assets": sum(row["asset_count"] for row in rows),
        "total_issues": sum(row["issue_count"] for row in rows),
        "issue_totals": dict(sum((Counter(row["issues"]) for row in rows), Counter())),
    }
    report = {
        "summary": summary,
        "packs": rows,
    }
    (output_dir / "pack_content_quality.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    lines = [
        "# Pack Content Quality Report",
        "",
        "## Summary",
        "",
        json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True),
        "",
        "## Root-Cause Claims",
        "",
        "- FACT: Generated asset quality is measured from runtime pack archives.",
        "- LIKELY: Low-information assets inherit low-information source chunks.",
        "- UNPROVEN: Better asset quality will follow automatically until cleaned chunks are regenerated into assets and re-audited.",
        "",
        "## Worst Packs",
        "",
        markdown_table(
            ["pack_id", "score", "assets", "issues", "empty_fc", "dup_quiz", "low_summary", "truncated_summary"],
            [[row["pack_id"], row["quality_score"], row["asset_count"], row["issue_count"], row["issues"]["empty_flashcards"], row["issues"]["duplicate_quizzes"], row["issues"]["low_info_summaries"], row["issues"]["truncated_summaries"]] for row in rows[:100]],
        ),
        "",
        "## Best Packs",
        "",
        markdown_table(
            ["pack_id", "score", "assets", "issues"],
            [[row["pack_id"], row["quality_score"], row["asset_count"], row["issue_count"]] for row in sorted(rows, key=lambda item: item["quality_score"], reverse=True)[:25]],
        ),
    ]
    (output_dir / "PACK_CONTENT_QUALITY_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

