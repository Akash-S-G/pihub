#!/usr/bin/env python3
"""Backfill textbook chapter sources and regenerate artifacts from local PDFs.

This script is intended for interrupted or partial curriculum generations.
It rebuilds chapter sources from the textbook PDFs when requested and then
regenerates the derived artifact files from that source.

Workflow:
1. Discover grade 6-10 textbook PDFs under `TEXTBOOKS`.
2. Create `textbook_artifacts/grade_*/subject/chapter_slug/source/chapter_source.json`
   for chapters that do not already have source content, or refresh existing
   source files when rebuilding.
3. Delegate artifact generation to `import_textbook_artifacts.py`, which
   rewrites the Kaggle-style artifact files from the extracted source.
4. Refresh chapter manifests so the output tree remains self-describing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
PACK_SERVICE_ROOT = REPO_ROOT / "pack-service"
for path in (REPO_ROOT, SCRIPTS_ROOT, PACK_SERVICE_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from import_textbook_artifacts import (  # noqa: E402
    EXPECTED_KAGGLE_ARTIFACTS,
    import_chapters,
    load_json_optional,
)


GRADE_RE = re.compile(r"\bclass\s*(10|[6-9])\b", re.I)
WORD_RE = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?")
HEADING_RE = re.compile(
    r"^(chapter\s+\d+|unit\s+\d+|\d+(?:\.\d+)*\s+.+|[A-Z][A-Z0-9 ,:;()'’–-]{5,})$",
    re.I,
)
FORMULA_RE = re.compile(
    r"("
    r"[A-Za-z][A-Za-z0-9_ ()]{0,40}\s*(?:=|∝|≤|≥|<|>)\s*[^.;\n]{1,120}"
    r"|[A-Z][a-z]?\s*=\s*[^.;\n]{1,120}"
    r"|[A-Za-z0-9]+\s*/\s*[A-Za-z0-9]+"
    r")"
)


@dataclass
class ChapterTarget:
    pdf_path: Path
    grade: int
    subject: str
    slug: str
    chapter_root: Path


def normalize_space(text: str) -> str:
    return re.sub(r"[ \t]+", " ", str(text or "").replace("\u00a0", " ")).strip()


def clean_text(text: str) -> str:
    value = normalize_space(text)
    value = value.replace("/square6", "•")
    value = value.replace("Reprint 2025-26", "")
    value = value.replace("Reprint 205-6", "")
    return normalize_space(value)


def slugify(value: str) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_") or "untitled"


def infer_grade(path: Path) -> int | None:
    for part in path.parts:
        match = GRADE_RE.search(part)
        if match:
            return int(match.group(1))
    return None


def infer_subject(path: Path, textbooks_root: Path) -> str:
    try:
        relative = path.relative_to(textbooks_root)
        return slugify(relative.parts[0]) if relative.parts else "unknown"
    except ValueError:
        return slugify(path.parent.name)


def chapter_target(pdf_path: Path, textbooks_root: Path, artifacts_root: Path) -> ChapterTarget:
    grade = infer_grade(pdf_path)
    if grade is None:
        raise ValueError(f"Could not infer grade from {pdf_path}")
    subject = infer_subject(pdf_path, textbooks_root)
    slug = slugify(pdf_path.stem)
    chapter_root = artifacts_root / f"grade_{grade}" / subject / slug
    return ChapterTarget(pdf_path=pdf_path, grade=grade, subject=subject, slug=slug, chapter_root=chapter_root)


def discover_pdfs(textbooks_root: Path, min_grade: int, max_grade: int) -> list[Path]:
    pdfs: list[Path] = []
    for path in sorted(textbooks_root.rglob("*.pdf")):
        grade = infer_grade(path)
        if grade is None or grade < min_grade or grade > max_grade:
            continue
        pdfs.append(path)
    return pdfs


def base_target_key(pdf_path: Path, textbooks_root: Path) -> tuple[int, str, str]:
    grade = infer_grade(pdf_path)
    if grade is None:
        raise ValueError(f"Could not infer grade from {pdf_path}")
    subject = infer_subject(pdf_path, textbooks_root)
    slug = slugify(pdf_path.stem)
    return grade, subject, slug


def text_from_structured_section(section: dict[str, Any]) -> str:
    parts = [clean_text(str(section.get("title") or "")), clean_text(str(section.get("content") or ""))]
    for item in section.get("subsections") or []:
        if isinstance(item, dict):
            parts.append(text_from_structured_section(item))
    return "\n\n".join(part for part in parts if part)


def flatten_structured_sections(raw_sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []

    def walk(section: dict[str, Any]) -> None:
        if not isinstance(section, dict):
            return
        text = clean_text(str(section.get("content") or ""))
        title = normalize_space(str(section.get("title") or "Untitled Section"))
        if text or title:
            sections.append(
                {
                    "title": title,
                    "text": text or title,
                    "level": int(section.get("level") or 1),
                }
            )
        for child in section.get("subsections") or []:
            if isinstance(child, dict):
                walk(child)

    for section in raw_sections:
        walk(section)
    return sections


def extract_with_pymupdf(pdf_path: Path) -> dict[str, Any]:
    import fitz  # type: ignore

    pages: list[str] = []
    images: list[dict[str, Any]] = []
    with fitz.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf, start=1):
            text = clean_text(page.get_text("text"))
            if text:
                pages.append(text)
            for img_index, img in enumerate(page.get_images(full=True), start=1):
                xref = img[0]
                base = pdf.extract_image(xref)
                if not base or not base.get("image"):
                    continue
                ext = base.get("ext", "png")
                images.append(
                    {
                        "file": f"images/page_{page_index:03d}_{img_index:02d}.{ext}",
                        "page": page_index,
                        "index": img_index,
                        "xref": xref,
                    }
                )
    source_text = "\n\n".join(pages)
    lines = [line for line in re.split(r"\n\s*\n", source_text) if line.strip()]
    sections = [
        {
            "title": f"Section {idx}",
            "text": clean_text(line),
            "level": 1 if idx == 1 else 2,
        }
        for idx, line in enumerate(lines[:200], start=1)
        if clean_text(line)
    ]
    if not sections and source_text:
        sections = [{"title": "Start", "text": source_text[:4000], "level": 1}]
    experiments = []
    for section in sections:
        blob = f"{section['title']} {section['text']}".lower()
        if any(marker in blob for marker in ("experiment", "activity", "investigation", "try this", "do this")):
            experiments.append({"title": section["title"], "text": section["text"][:2500], "kind": "experiment_or_activity"})
    formulas = []
    for match in FORMULA_RE.finditer(source_text):
        formula = clean_text(match.group(0))
        if formula and formula not in formulas and len(formula) <= 120:
            formulas.append(formula)
    return {
        "extractor": "pymupdf",
        "chapter_title": pdf_path.stem.replace("_", " ").title(),
        "source_text": source_text,
        "sections": sections,
        "experiments": experiments[:20],
        "formulas": formulas[:20],
        "images": images[:50],
    }


def extract_from_structured(structured_path: Path) -> dict[str, Any]:
    raw = json.loads(structured_path.read_text(encoding="utf-8"))
    sections = flatten_structured_sections(list(raw.get("sections") or []))
    source_parts = [text_from_structured_section(section) for section in list(raw.get("sections") or []) if isinstance(section, dict)]
    source_text = clean_text("\n\n".join(part for part in source_parts if part))
    if not source_text:
        source_text = clean_text(str(raw.get("source_text") or ""))
    experiments = []
    for section in sections:
        blob = f"{section['title']} {section['text']}".lower()
        if any(marker in blob for marker in ("experiment", "activity", "investigation", "try this", "do this")):
            experiments.append({"title": section["title"], "text": section["text"][:2500], "kind": "experiment_or_activity"})
    formulas = []
    for section in list(raw.get("sections") or []):
        if not isinstance(section, dict):
            continue
        for equation in section.get("equations") or []:
            equation = clean_text(str(equation))
            if equation and equation not in formulas and len(equation) <= 120:
                formulas.append(equation)
    for match in FORMULA_RE.finditer(source_text):
        formula = clean_text(match.group(0))
        if formula and formula not in formulas and len(formula) <= 120:
            formulas.append(formula)
    images = []
    for idx, figure in enumerate(raw.get("figures") or [], start=1):
        if not isinstance(figure, dict):
            continue
        caption = clean_text(str(figure.get("caption") or ""))
        images.append(
            {
                "file": figure.get("file") or f"images/figure_{idx:02d}.png",
                "page": figure.get("page"),
                "index": figure.get("index", idx),
                "caption": caption,
            }
        )
    return {
        "extractor": str(raw.get("extractor") or "docling"),
        "chapter_title": str(raw.get("chapter_title") or raw.get("document_title") or "Untitled Chapter"),
        "source_text": source_text,
        "sections": sections,
        "experiments": experiments[:20],
        "formulas": formulas[:20],
        "images": images[:50],
    }


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_source_payload(target: ChapterTarget, textbooks_root: Path, structured_root: Path) -> dict[str, Any]:
    structured_path = structured_root / f"grade_{target.grade}" / target.subject / target.slug / "structured_chapter.json"
    if structured_path.exists():
        extracted = extract_from_structured(structured_path)
    else:
        extracted = extract_with_pymupdf(target.pdf_path)

    source_text = clean_text(str(extracted.get("source_text") or ""))
    sections = list(extracted.get("sections") or [])
    if not sections and source_text:
        sections = [{"title": "Start", "text": source_text[:4000], "level": 1}]

    payload = {
        "pdf_path": str(target.pdf_path),
        "grade": target.grade,
        "subject": target.subject,
        "chapter_slug": target.slug,
        "pdf_hash": file_hash(target.pdf_path),
        "chapter_title": clean_text(str(extracted.get("chapter_title") or target.slug.replace("_", " ").title())),
        "extractor": extracted.get("extractor") or "pymupdf",
        "source_text": source_text or clean_text(target.pdf_path.stem.replace("_", " ")),
        "sections": sections,
        "experiments": extracted.get("experiments") or [],
        "formulas": extracted.get("formulas") or [],
        "images": extracted.get("images") or [],
    }
    return payload


def ensure_source_and_manifest(
    target: ChapterTarget,
    textbooks_root: Path,
    structured_root: Path,
    refresh_source: bool,
) -> bool:
    source_dir = target.chapter_root / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_path = source_dir / "chapter_source.json"
    manifest_path = target.chapter_root / "manifest.json"

    created = False
    if refresh_source or not source_path.exists():
        payload = build_source_payload(target, textbooks_root, structured_root)
        source_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        (source_dir / "chapter_source.txt").write_text(payload["source_text"], encoding="utf-8")
        (source_dir / "sections.json").write_text(json.dumps(payload["sections"], indent=2, ensure_ascii=False), encoding="utf-8")
        (source_dir / "experiments.json").write_text(json.dumps(payload["experiments"], indent=2, ensure_ascii=False), encoding="utf-8")
        (source_dir / "images.json").write_text(json.dumps(payload["images"], indent=2, ensure_ascii=False), encoding="utf-8")
        created = True

    source = load_json_optional(source_path)
    if not isinstance(source, dict):
        raise ValueError(f"Failed to load source for {target.chapter_root}")

    manifest = dict(source)
    manifest["status"] = "complete"
    manifest["artifacts"] = {
        "chapter_notes": "artifacts/chapter_notes.json",
        "summary": "artifacts/summary.json",
        "key_points": "artifacts/key_points.json",
        "concepts": "artifacts/concepts.json",
        "glossary": "artifacts/glossary.json",
        "misconceptions": "artifacts/misconceptions.json",
        "applications": "artifacts/applications.json",
        "flashcards": "artifacts/flashcards.json",
        "quizzes": "artifacts/quizzes.json",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return created


def update_manifest_artifacts(target: ChapterTarget) -> None:
    manifest_path = target.chapter_root / "manifest.json"
    source_path = target.chapter_root / "source" / "chapter_source.json"
    if not source_path.exists():
        return
    source = json.loads(source_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else dict(source)
    artifact_map: dict[str, str] = {}
    for filename in EXPECTED_KAGGLE_ARTIFACTS:
        file_path = target.chapter_root / "artifacts" / filename
        if file_path.exists():
            artifact_map[filename.removesuffix(".json")] = str(file_path.relative_to(target.chapter_root))
    manifest.update(source)
    manifest["status"] = "complete"
    manifest["artifacts"] = artifact_map or manifest.get("artifacts", {})
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def backfill(
    textbooks_root: Path,
    artifacts_root: Path,
    structured_root: Path,
    min_grade: int,
    max_grade: int,
    refresh_source: bool,
    sync_packs: bool,
    storage_root: Path,
) -> dict[str, Any]:
    pdfs = discover_pdfs(textbooks_root, min_grade, max_grade)
    key_counts: dict[tuple[int, str, str], int] = {}
    key_last_index: dict[tuple[int, str, str], int] = {}
    for index, pdf_path in enumerate(pdfs):
        key = base_target_key(pdf_path, textbooks_root)
        key_counts[key] = key_counts.get(key, 0) + 1
        key_last_index[key] = index

    created_sources = 0
    targets: list[ChapterTarget] = []

    for index, pdf_path in enumerate(pdfs):
        grade, subject, slug = base_target_key(pdf_path, textbooks_root)
        key = (grade, subject, slug)
        if key_counts.get(key, 0) > 1 and key_last_index.get(key) != index:
            slug = f"{slug}_{slugify(pdf_path.parent.name)}"
        target = ChapterTarget(
            pdf_path=pdf_path,
            grade=grade,
            subject=subject,
            slug=slug,
            chapter_root=artifacts_root / f"grade_{grade}" / subject / slug,
        )
        targets.append(target)
        if ensure_source_and_manifest(target, textbooks_root, structured_root, refresh_source=refresh_source):
            created_sources += 1

    import_report = import_chapters(
        root=artifacts_root,
        storage_root=storage_root,
        replace_existing=True,
        min_grade=min_grade,
        max_grade=max_grade,
        dry_run=False,
        sync_packs=sync_packs,
    )

    for target in targets:
        update_manifest_artifacts(target)

    summary = {
        "pdf_count": len(pdfs),
        "chapter_roots": len(targets),
        "source_files_written": created_sources,
        "manifest_files_updated": len(targets),
        "import_summary": import_report["summary"],
        "artifacts_root": str(artifacts_root),
        "textbooks_root": str(textbooks_root),
        "structured_root": str(structured_root),
        "storage_root": str(storage_root),
        "sync_packs": sync_packs,
    }
    return {"summary": summary, "import_report": import_report}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill missing textbook chapters and artifacts.")
    parser.add_argument("--textbooks-root", default="TEXTBOOKS", help="Root folder containing textbook PDFs.")
    parser.add_argument("--artifacts-root", default="textbook_artifacts", help="Root folder for textbook artifact chapters.")
    parser.add_argument("--structured-root", default="docling_structured_chapters", help="Root folder for structured chapter cache.")
    parser.add_argument("--min-grade", type=int, default=6)
    parser.add_argument("--max-grade", type=int, default=10)
    parser.add_argument("--refresh-source", action="store_true", help="Rewrite source files even if they already exist.")
    parser.add_argument("--sync-packs", action="store_true", help="Also sync derived packs into the configured pack storage.")
    parser.add_argument("--storage-root", default=str(Path("/tmp") / "pihub_textbook_pack_storage"), help="Pack storage root used by the importer.")
    parser.add_argument("--output-dir", default=str(Path("/tmp") / "textbook_artifacts_backfill_report"), help="Directory for the backfill report.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    textbooks_root = Path(args.textbooks_root)
    artifacts_root = Path(args.artifacts_root)
    structured_root = Path(args.structured_root)
    storage_root = Path(args.storage_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    report = backfill(
        textbooks_root=textbooks_root,
        artifacts_root=artifacts_root,
        structured_root=structured_root,
        min_grade=args.min_grade,
        max_grade=args.max_grade,
        refresh_source=bool(args.refresh_source),
        sync_packs=bool(args.sync_packs),
        storage_root=storage_root,
    )
    report_path = output_dir / "textbook_artifacts_backfill_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
