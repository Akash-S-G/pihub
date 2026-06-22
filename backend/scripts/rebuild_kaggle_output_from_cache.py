#!/usr/bin/env python3
"""Rebuild Kaggle curriculum artifact outputs from cached per-section generations.

This is a salvage tool for interrupted Kaggle runs. It does not call a model and
does not modify the original cache. It reconstructs final artifact JSON files by
recomputing the notebook cache key:

    sha256(section_id + artifact_name + enriched_section_text)

The rebuilt output is written to a separate folder by default.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ARTIFACT_SPECS: dict[str, str] = {
    "concepts": "concepts.json",
    "learning_objectives": "learning_objectives.json",
    "glossary": "glossary.json",
    "summary": "summary.json",
    "detailed_explanation": "detailed_explanation.json",
    "misconceptions": "misconceptions.json",
    "mcq_quiz": "mcq_quiz.json",
    "short_answer_questions": "short_answer_questions.json",
    "flashcards": "flashcards.json",
    "concept_relationships": "concept_relationships.json",
    "image_captions": "image_captions.json",
    "investigations": "investigations.json",
    "teacher_notes": "teacher_notes.json",
    "prerequisites": "prerequisites.json",
    "difficulty_analysis": "difficulty_analysis.json",
}


@dataclass
class FigureData:
    figure_id: str
    caption: str = ""


@dataclass
class SectionData:
    section_id: str
    title: str
    content: str
    tables: list[dict[str, Any]] = field(default_factory=list)
    figures: list[FigureData] = field(default_factory=list)
    equations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChapterData:
    document_id: str
    document_title: str
    chapter_title: str
    grade: str
    subject: str
    sections: list[SectionData]
    source_pdf: str = ""


def adapt_section(raw: dict[str, Any]) -> SectionData:
    return SectionData(
        section_id=str(raw.get("section_id") or hashlib.sha256(str(raw).encode()).hexdigest()[:16]),
        title=str(raw.get("title") or "Untitled Section"),
        content=str(raw.get("content") or ""),
        tables=list(raw.get("tables") or []),
        figures=[
            FigureData(figure_id=str(fig.get("figure_id") or ""), caption=str(fig.get("caption") or ""))
            for fig in raw.get("figures", [])
            if isinstance(fig, dict)
        ],
        equations=list(raw.get("equations") or []),
        metadata=dict(raw.get("metadata") or {}),
    )


def adapt_chapter(raw: dict[str, Any]) -> ChapterData:
    return ChapterData(
        document_id=str(raw.get("document_id") or hashlib.sha256(str(raw).encode()).hexdigest()[:16]),
        document_title=str(raw.get("document_title") or "Untitled Document"),
        chapter_title=str(raw.get("chapter_title") or raw.get("document_title") or "Untitled Chapter"),
        grade=str(raw.get("grade") or ""),
        subject=str(raw.get("subject") or ""),
        sections=[adapt_section(section) for section in raw.get("sections", [])],
        source_pdf=str(raw.get("source_pdf") or ""),
    )


def enriched_section_text(section: SectionData) -> str:
    parts = [f"Section Title: {section.title}", section.content]
    if section.equations:
        parts.append("Equations:\n" + "\n".join(section.equations[:20]))
    if section.tables:
        table_lines = [json.dumps(table, ensure_ascii=False)[:2500] for table in section.tables[:5]]
        parts.append("Tables:\n" + "\n".join(table_lines))
    captions = [f"{fig.figure_id}: {fig.caption}" for fig in section.figures if fig.caption]
    if captions:
        parts.append("Figure references and captions:\n" + "\n".join(captions[:20]))
    return "\n\n".join(part for part in parts if part).strip()


def cache_path(cache_root: Path, section: SectionData, artifact_name: str) -> Path:
    digest = hashlib.sha256(
        (section.section_id + artifact_name + enriched_section_text(section)).encode("utf-8")
    ).hexdigest()
    return cache_root / f"{digest}.json"


def legacy_chapter_cache_path(cache_root: Path, chapter: ChapterData, artifact_name: str) -> Path:
    """Cache key used by an earlier Kaggle notebook revision.

    Older runs generated one payload per chapter and keyed it with:
    document_id + artifact_name + chapter_title
    """

    digest = hashlib.sha256(
        (chapter.document_id + artifact_name + chapter.chapter_title).encode("utf-8")
    ).hexdigest()
    return cache_root / f"{digest}.json"


def payload_is_empty(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    meaningful_keys = [key for key in payload.keys() if not key.startswith("_")]
    if not meaningful_keys:
        return True
    empty_values = 0
    for key in meaningful_keys:
        value = payload.get(key)
        if value is None:
            empty_values += 1
        elif isinstance(value, str) and not value.strip():
            empty_values += 1
        elif isinstance(value, list) and len(value) == 0:
            empty_values += 1
        elif isinstance(value, dict) and len(value) == 0:
            empty_values += 1
    return empty_values == len(meaningful_keys)


def list_structured_chapters(root: Path) -> list[ChapterData]:
    chapters: list[ChapterData] = []
    for path in sorted(root.rglob("structured_chapter.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        chapters.append(adapt_chapter(raw))
    return chapters


def rebuild(input_root: Path, output_root: Path) -> dict[str, Any]:
    cache_root = input_root / "cache"
    structured_root = input_root / "structured_chapters"
    pack_root = output_root / "generated_pack"
    pack_root.mkdir(parents=True, exist_ok=True)

    chapters = list_structured_chapters(structured_root)
    sections = [section for chapter in chapters for section in chapter.sections]

    artifacts: dict[str, list[dict[str, Any]]] = {name: [] for name in ARTIFACT_SPECS}
    missing: dict[str, list[dict[str, str]]] = {name: [] for name in ARTIFACT_SPECS}
    empty_payloads: dict[str, int] = {name: 0 for name in ARTIFACT_SPECS}
    bad_json: dict[str, int] = {name: 0 for name in ARTIFACT_SPECS}
    source_mode: dict[str, str] = {name: "none" for name in ARTIFACT_SPECS}

    chapter_by_section: dict[str, ChapterData] = {}
    for chapter in chapters:
        for section in chapter.sections:
            chapter_by_section[section.section_id] = chapter

    # Prefer current section-level cache entries when they exist.
    for artifact_name in ARTIFACT_SPECS:
        section_entries: list[dict[str, Any]] = []
        section_missing: list[dict[str, str]] = []
        section_empty = 0
        section_bad = 0
        for section in sections:
            chapter = chapter_by_section[section.section_id]
            path = cache_path(cache_root, section, artifact_name)
            if not path.exists():
                section_missing.append(
                    {
                        "chapter_id": chapter.document_id,
                        "chapter_title": chapter.chapter_title,
                        "section_id": section.section_id,
                        "section_title": section.title,
                    }
                )
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                section_bad += 1
                continue
            if payload_is_empty(payload):
                section_empty += 1
            section_entries.append(
                {
                    "chapter_id": chapter.document_id,
                    "chapter_title": chapter.chapter_title,
                    "grade": chapter.grade,
                    "subject": chapter.subject,
                    "section_id": section.section_id,
                    "section_title": section.title,
                    "payload": payload,
                    "cache_mode": "section",
                }
            )

        if section_entries:
            artifacts[artifact_name] = section_entries
            missing[artifact_name] = section_missing
            empty_payloads[artifact_name] = section_empty
            bad_json[artifact_name] = section_bad
            source_mode[artifact_name] = "section"
            continue

        # Fall back to the legacy chapter-level cache used by the copied output.
        chapter_entries: list[dict[str, Any]] = []
        chapter_missing: list[dict[str, str]] = []
        chapter_empty = 0
        chapter_bad = 0
        for chapter in chapters:
            path = legacy_chapter_cache_path(cache_root, chapter, artifact_name)
            if not path.exists():
                chapter_missing.append(
                    {
                        "chapter_id": chapter.document_id,
                        "chapter_title": chapter.chapter_title,
                    }
                )
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                chapter_bad += 1
                continue
            if payload_is_empty(payload):
                chapter_empty += 1
            chapter_entries.append(
                {
                    "chapter_id": chapter.document_id,
                    "chapter_title": chapter.chapter_title,
                    "grade": chapter.grade,
                    "subject": chapter.subject,
                    "payload": payload,
                    "cache_mode": "legacy_chapter",
                }
            )

        artifacts[artifact_name] = chapter_entries
        missing[artifact_name] = chapter_missing
        empty_payloads[artifact_name] = chapter_empty
        bad_json[artifact_name] = chapter_bad
        source_mode[artifact_name] = "legacy_chapter" if chapter_entries else "none"

    for artifact_name, file_name in ARTIFACT_SPECS.items():
        (pack_root / file_name).write_text(
            json.dumps(artifacts[artifact_name], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    coverage: dict[str, Any] = {}
    total_sections = len(sections)
    total_chapters = len(chapters)
    for artifact_name, entries in artifacts.items():
        denominator = total_sections if source_mode[artifact_name] == "section" else total_chapters
        coverage[artifact_name] = {
            "cache_mode": source_mode[artifact_name],
            "entries": len(entries),
            "missing": len(missing[artifact_name]),
            "bad_json": bad_json[artifact_name],
            "empty_payloads": empty_payloads[artifact_name],
            "coverage": round(len(entries) / denominator, 4) if denominator else 0,
            "non_empty_coverage": round((len(entries) - empty_payloads[artifact_name]) / denominator, 4)
            if denominator
            else 0,
        }

    concept_counts: list[int] = []
    for entry in artifacts["concepts"]:
        payload = entry.get("payload", {})
        items = payload.get("items")
        if items is None:
            items = payload.get("concepts")
        concept_counts.append(len(items) if isinstance(items, list) else 0)

    report = {
        "input_root": str(input_root),
        "output_root": str(output_root),
        "chapters": len(chapters),
        "sections": total_sections,
        "artifacts": coverage,
        "concept_quality": {
            "average_items": round(statistics.mean(concept_counts), 2) if concept_counts else 0,
            "median_items": statistics.median(concept_counts) if concept_counts else 0,
            "empty_concept_entries": sum(1 for count in concept_counts if count == 0),
        },
    }

    (pack_root / "CACHE_REBUILD_REPORT.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    zip_path = output_root / "generated_pack_from_cache.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(pack_root.rglob("*.json")):
            archive.write(file_path, file_path.relative_to(output_root))
    report["zip_path"] = str(zip_path)
    report["zip_size_bytes"] = zip_path.stat().st_size
    (pack_root / "CACHE_REBUILD_REPORT.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", default="idp_curriculum_generation")
    parser.add_argument("--output-root", default="idp_curriculum_generation_rebuilt")
    args = parser.parse_args()

    report = rebuild(Path(args.input_root), Path(args.output_root))
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
