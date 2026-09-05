#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import random
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK_SERVICE_ROOT = REPO_ROOT / "pack-service"
for path in (REPO_ROOT, PACK_SERVICE_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.pack_storage.pack_repository import PackRepository  # noqa: E402


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def write_json_preserve(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_json_optional(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return load_json(path)
    except Exception:
        return None


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("\u00a0", " ")).strip()


def clean_text(text: str) -> str:
    value = normalize_space(text)
    value = value.replace("/square6", "•")
    value = value.replace("Reprint 2025-26", "")
    value = value.replace("Reprint 205-6", "")
    return normalize_space(value)


STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "for", "from", "has", "have", "in", "is", "it",
    "its", "of", "on", "or", "that", "the", "their", "this", "to", "was", "were", "when", "which", "with",
    "we", "you", "your", "they", "them", "these", "those", "there", "here", "into", "than", "then", "than",
}

EXCLUDED_RUNTIME_CHAPTERS = {"introduction", "answers"}


def is_noise(text: str) -> bool:
    value = clean_text(text).lower()
    if not value:
        return True
    if "/square6" in value or "reprint" in value:
        return True
    if value in {"tawa/pan", "chapter notes"}:
        return True
    tokens = re.findall(r"[a-z0-9]+", value)
    if not tokens:
        return True
    if len(tokens) <= 1 and len(value) < 4:
        return True
    return False


def normalize_term(text: str) -> str:
    value = clean_text(text)
    value = re.sub(r"^[^A-Za-z]+|[^A-Za-z0-9/ -]+$", "", value).strip()
    value = re.sub(r"\s+", " ", value)
    return value


def derive_term_from_fact(fact: str, fallback: str) -> str:
    text = clean_text(fact)
    patterns = [
        r"^([A-Za-z][A-Za-z0-9' -]{2,80}?)\s+(?:are|is|means|refers to|includes|include|involves|helps|shows|illustrates|requires|must|can|provides|describes|explains|evidences|demonstrates)\b",
        r"^([A-Za-z][A-Za-z0-9' -]{2,80}?)\s+that\b",
    ]
    for pattern in patterns:
        match = re.match(pattern, text, flags=re.I)
        if match:
            candidate = normalize_term(match.group(1))
            if candidate and not is_noise(candidate):
                return candidate
    candidate = normalize_term(" ".join(text.split()[:6]))
    return candidate if candidate and not is_noise(candidate) else fallback


def sentence_case(text: str) -> str:
    value = clean_text(text)
    return value[:1].upper() + value[1:] if value else value


def dedupe_by_key(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        value = normalize_space(str(item.get(key) or "")).lower()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(item)
    return result


def is_runtime_excluded_chapter(chapter: str | None) -> bool:
    return slugify(chapter or "") in EXCLUDED_RUNTIME_CHAPTERS


def clean_summary_text(text: str) -> str:
    value = normalize_space(text)
    value = re.sub(r"^(?:[A-Z0-9]{2,}\s+)+", "", value)
    value = re.sub(r"^(?:\d+\s+)+", "", value)
    value = re.sub(r"^(?:[A-Z]{2,}\s+\d+\s+)+", "", value)
    value = re.sub(r"^(?:CH\d+\s+)+", "", value, flags=re.I)
    value = re.sub(r"^(?:REPRINT\s+\d{4}-\d{2}\s+)+", "", value, flags=re.I)
    value = re.sub(r"^(?:MATHEMATICS|SCIENCE|SOCIAL SCIENCE)\s+\d+\s+", "", value, flags=re.I)
    return normalize_space(value)


def sentence_split(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", normalize_space(text))
    return [part.strip() for part in parts if part and part.strip()]


def source_section_texts(source: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for section in source.get("sections") or []:
        if not isinstance(section, dict):
            continue
        title = clean_text(str(section.get("title") or ""))
        body = clean_text(str(section.get("text") or section.get("content") or ""))
        if title.lower() in {"start", "untitled section"} or re.fullmatch(r"section\s*\d+", title.lower() or ""):
            combined = clean_summary_text(body)
        else:
            combined = clean_summary_text(" ".join(part for part in (title, body) if part))
        if not combined or is_noise(combined):
            continue
        texts.append(combined)
    return texts


def summarize_source_text(source: dict[str, Any], chapter_title: str) -> dict[str, Any]:
    source_text = clean_summary_text(str(source.get("source_text") or ""))
    section_texts = source_section_texts(source)
    candidate_texts = [text for text in section_texts if text]
    if not candidate_texts and source_text:
        candidate_texts = sentence_split(source_text)

    overview_parts: list[str] = []
    for text in candidate_texts[:4]:
        if len(text) < 20 or is_noise(text):
            continue
        overview_parts.append(clean_summary_text(text))
        if len(" ".join(overview_parts)) >= 1000:
            break
    overview = normalize_space(" ".join(overview_parts)) if overview_parts else sentence_case(source_text[:420] or chapter_title)
    if len(overview) > 1100:
        cutoff = overview.rfind(". ", 0, 1050)
        overview = overview[: cutoff + 1] if cutoff > 0 else overview[:1050].rstrip()

    key_points: list[str] = []
    for text in candidate_texts:
        if len(key_points) >= 5:
            break
        if is_noise(text):
            continue
        sentences = sentence_split(text)
        snippet = sentences[0] if sentences else text
        snippet = normalize_space(snippet)
        if snippet and snippet not in key_points:
            key_points.append(snippet[:220])

    if len(key_points) < 5 and source_text:
        for sentence in sentence_split(source_text):
            if len(key_points) >= 5:
                break
            sentence = normalize_space(sentence)
            if not sentence or is_noise(sentence):
                continue
            if sentence not in key_points:
                key_points.append(sentence[:220])

    formulas = [clean_text(str(item)) for item in source.get("formulas") or [] if clean_text(str(item)) and not is_noise(str(item))]
    experiments = [clean_text(str(item)) for item in source.get("experiments") or [] if clean_text(str(item)) and not is_noise(str(item))]

    return {
        "chapter_title": chapter_title,
        "overview": sentence_case(overview),
        "summary": sentence_case(overview),
        "key_points": key_points[:5],
        "important_formulas": formulas[:10],
        "experiments": experiments[:10],
    }


def fact_bank_from_source(
    source: dict[str, Any],
    summary: dict[str, Any],
    chapter_title: str,
    chapter_notes: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    facts: list[dict[str, str]] = []
    overview = clean_text(str(summary.get("overview") or summary.get("summary") or ""))
    if overview and not is_noise(overview):
        facts.append({"term": chapter_title, "fact": sentence_case(overview), "source": "overview"})

    for item in summary.get("key_points") or []:
        fact = clean_text(str(item))
        if not fact or is_noise(fact):
            continue
        term = derive_term_from_fact(fact, chapter_title)
        facts.append({"term": term, "fact": sentence_case(fact), "source": "key_point"})

    for item in summary.get("important_formulas") or []:
        formula = clean_text(str(item))
        if not formula or is_noise(formula):
            continue
        term = re.sub(r"\s*\([^)]+\)\s*$", "", formula).strip()
        facts.append({"term": term or chapter_title, "fact": f"The chapter highlights the formula {formula}.", "source": "formula"})

    for item in summary.get("experiments") or []:
        experiment = clean_text(str(item))
        if not experiment or is_noise(experiment):
            continue
        facts.append({"term": derive_term_from_fact(experiment, "Activity"), "fact": sentence_case(experiment), "source": "experiment"})

    notes = chapter_notes or {}
    for item in notes.get("core_points") or []:
        point = clean_text(str(item))
        if not point or is_noise(point):
            continue
        facts.append({"term": derive_term_from_fact(point, chapter_title), "fact": sentence_case(point), "source": "chapter_note"})

    for item in notes.get("key_terms") or []:
        term = clean_text(str(item))
        if not term or is_noise(term):
            continue
        facts.append({"term": term, "fact": f"{term} is an important idea from the chapter.", "source": "key_term"})

    if not facts:
        chapter_text = clean_text(str(source.get("source_text") or ""))
        if chapter_text:
            facts.append({"term": chapter_title, "fact": sentence_case(chapter_text[:240]), "source": "source_text"})

    return dedupe_by_key(facts, "term")


def make_concepts_from_facts(facts: list[dict[str, str]], limit: int = 10) -> list[dict[str, Any]]:
    concepts: list[dict[str, Any]] = []
    for idx, fact in enumerate(facts[:limit], start=1):
        concepts.append(
            {
                "concept": fact["term"],
                "description": fact["fact"],
                "category": fact["source"],
                "concept_id": f"concept_{idx:03d}",
            }
        )
    return concepts


def make_glossary_from_facts(facts: list[dict[str, str]], chapter_title: str, limit: int = 12) -> list[dict[str, Any]]:
    glossary: list[dict[str, Any]] = []
    for idx, fact in enumerate(facts[:limit], start=1):
        glossary.append(
            {
                "term": fact["term"],
                "definition": fact["fact"],
                "example": f"In {chapter_title.lower()}, this idea appears as a core concept.",
                "glossary_id": f"glossary_{idx:03d}",
            }
        )
    return glossary


def make_flashcards_from_facts(facts: list[dict[str, str]], limit: int = 15) -> list[dict[str, Any]]:
    flashcards: list[dict[str, Any]] = []
    for idx, fact in enumerate(facts[:limit], start=1):
        flashcards.append(
            {
                "flashcard_id": f"flashcard_{idx:03d}",
                "front": f"What does the chapter say about {fact['term']}?",
                "back": fact["fact"],
            }
        )
    return flashcards


def make_misconceptions_from_facts(facts: list[dict[str, str]], chapter_title: str, limit: int = 8) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for idx, fact in enumerate(facts[:limit], start=1):
        items.append(
            {
                "misconception": f"Confusing {fact['term']} with an unrelated idea",
                "correction": fact["fact"],
                "why_students_confuse_it": f"The chapter's {chapter_title.lower()} vocabulary can make {fact['term']} easy to mix up with other terms.",
                "misconception_id": f"misconception_{idx:03d}",
            }
        )
    return items


def make_applications_from_facts(facts: list[dict[str, str]], chapter_title: str, limit: int = 8) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for idx, fact in enumerate(facts[:limit], start=1):
        items.append(
            {
                "application": f"Use {fact['term']} to interpret a real example from {chapter_title.lower()}",
                "example": fact["fact"],
                "application_id": f"application_{idx:03d}",
            }
        )
    return items


def _quiz_distractors(facts: list[dict[str, str]], current_fact: dict[str, str], chapter_title: str) -> list[str]:
    distractors = [item["fact"] for item in facts if item["fact"] != current_fact["fact"]]
    random.shuffle(distractors)
    candidates = distractors[:3]
    generic = [
        f"It is unrelated to {chapter_title.lower()}.",
        "It is only a memorization trick with no meaning.",
        f"It is the opposite of {current_fact['term']}.",
        "It is a completely different chapter idea.",
    ]
    while len(candidates) < 3:
        fallback = generic[len(candidates) % len(generic)]
        if fallback not in candidates and fallback != current_fact["fact"]:
            candidates.append(fallback)
        else:
            candidates.append(fallback + f" {len(candidates) + 1}")
    return candidates[:3]


def make_quizzes_from_facts(facts: list[dict[str, str]], chapter_title: str, count: int = 20) -> list[dict[str, Any]]:
    if not facts:
        return []
    random.seed(17)
    pool = facts[:]
    quizzes: list[dict[str, Any]] = []
    templates = [
        "Which statement best describes {term}?",
        "What does the chapter say about {term}?",
        "Which idea from {chapter} matches {term}?",
        "How is {term} presented in the chapter?",
    ]
    for idx in range(count):
        fact = pool[idx % len(pool)]
        options = [fact["fact"], *_quiz_distractors(pool, fact, chapter_title)]
        random.shuffle(options)
        quizzes.append(
            {
                "question": templates[idx % len(templates)].format(term=fact["term"], chapter=chapter_title),
                "answer": fact["fact"],
                "options": options[:4],
                "explanation": f"The chapter explains {fact['term']} as: {fact['fact']}",
            }
        )
    return quizzes


def slugify(value: str) -> str:
    value = normalize_space(value).lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return re.sub(r"_+", "_", value).strip("_") or "unknown"


def chapter_pack_id(grade: int | None, subject: str | None, chapter: str | None, language: str = "english") -> str:
    grade_part = f"{int(grade)}" if grade is not None else "unknown"
    return f"chapter_{grade_part}_{slugify(subject or 'unknown')}_{slugify(chapter or 'general')}_{slugify(language)}"


def chapter_quality_score(source_text: str, summary_text: str, quizzes: list[dict[str, Any]], flashcards: list[dict[str, Any]]) -> dict[str, Any]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9'-]{2,}", source_text.lower())
    summary_len = len(summary_text)
    generic_quizzes = sum(
        1
        for item in quizzes
        if isinstance(item, dict)
        and (
            "chapter notes" in str(item.get("answer") or item.get("correct_answer") or "").lower()
            or "chapter notes" in str(item.get("explanation") or "").lower()
        )
    )
    generic_flashcards = sum(
        1
        for item in flashcards
        if isinstance(item, dict)
        and (
            "chapter notes" in str(item.get("back") or "").lower()
            or "review the chapter notes" in str(item.get("back") or "").lower()
        )
    )
    noise_flags = sum(1 for marker in ("/square6", "reprint 2025-26", "reprint 205-6") if marker in source_text.lower())
    density = len(set(tokens)) / max(1, len(tokens))
    score = 100.0
    score -= 15.0 * noise_flags
    score -= 20.0 * (generic_quizzes / max(1, len(quizzes)))
    score -= 20.0 * (generic_flashcards / max(1, len(flashcards)))
    score -= 10.0 if summary_len < 700 else 0.0
    score += 5.0 * min(1.0, density)
    return {
        "quality_score": round(max(0.0, min(100.0, score)), 2),
        "generic_quiz_count": generic_quizzes,
        "generic_flashcard_count": generic_flashcards,
        "noise_flags": noise_flags,
        "summary_chars": summary_len,
    }


def normalize_content_sections(source: dict[str, Any]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for idx, section in enumerate(source.get("sections") or [], start=1):
        if not isinstance(section, dict):
            continue
        text = clean_text(str(section.get("text") or section.get("content") or ""))
        if not text:
            continue
        title = normalize_space(str(section.get("title") or f"Section {idx}"))
        sections.append(
            {
                "chunk_id": f"section_{idx:03d}",
                "title": title,
                "text": text,
                "metadata": {
                    "section_index": idx,
                    "kind": "chapter_section",
                    "page": section.get("page"),
                },
            }
        )

    if not sections:
        text = clean_text(str(source.get("source_text") or ""))
        if text:
            sections.append(
                {
                    "chunk_id": "section_001",
                    "title": normalize_space(str(source.get("chapter_title") or "Main Lesson")),
                    "text": text,
                    "metadata": {"section_index": 1, "kind": "chapter_source"},
                }
            )
    return sections


def normalize_summary(summary: dict[str, Any], chapter_title: str) -> list[dict[str, Any]]:
    overview = clean_text(str(summary.get("overview") or summary.get("summary") or ""))
    key_points = [sentence_case(item) for item in summary.get("key_points") or [] if clean_text(str(item)) and not is_noise(str(item))]
    formulas = [clean_text(str(item)) for item in summary.get("important_formulas") or [] if clean_text(str(item)) and not is_noise(str(item))]
    experiments = [sentence_case(item) for item in summary.get("experiments") or [] if clean_text(str(item)) and not is_noise(str(item))]
    return [
        {
            "title": chapter_title,
            "text": sentence_case(overview) if overview else chapter_title,
            "topic": chapter_title,
            "key_points": key_points,
            "important_formulas": formulas,
            "experiments": experiments,
        }
    ]


def normalize_quizzes(facts: list[dict[str, str]], chapter_title: str) -> list[dict[str, Any]]:
    return make_quizzes_from_facts(facts, chapter_title, count=20)


def normalize_flashcards(facts: list[dict[str, str]]) -> list[dict[str, Any]]:
    return make_flashcards_from_facts(facts, limit=15)


def normalize_simple_list(items: list[dict[str, Any]], text_keys: tuple[str, ...], id_prefix: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        text_value = ""
        for key in text_keys:
            text_value = clean_text(str(item.get(key) or ""))
            if text_value:
                break
        if not text_value:
            continue
        if is_noise(text_value):
            continue
        result.append({f"{id_prefix}_id": f"{id_prefix}_{idx:03d}", **{key: clean_text(str(value)) if isinstance(value, str) else value for key, value in item.items()}})
    return result


EXPECTED_KAGGLE_ARTIFACTS = (
    "summary.json",
    "key_points.json",
    "concepts.json",
    "glossary.json",
    "misconceptions.json",
    "applications.json",
    "flashcards.json",
    "quizzes.json",
    "chapter_notes.json",
)


def build_chapter_notes(summary: dict[str, Any], facts: list[dict[str, str]], chapter_title: str, source: dict[str, Any]) -> dict[str, Any]:
    core_points = [fact["fact"] for fact in facts[:7]]
    if not core_points:
        core_points = [sentence_case(str(item)) for item in summary.get("key_points") or [] if clean_text(str(item))]
    key_terms = [fact["term"] for fact in facts[:8]]
    important_formulas = [clean_text(str(item)) for item in source.get("formulas") or [] if clean_text(str(item))]
    experiments = [clean_text(str(item)) for item in source.get("experiments") or [] if clean_text(str(item))]
    return {
        "chapter_notes": {
            "chapter_title": chapter_title,
            "one_sentence_summary": clean_text(str(summary.get("overview") or summary.get("summary") or chapter_title)),
            "core_points": core_points,
            "key_terms": key_terms,
            "important_formulas": important_formulas,
            "experiments": experiments,
            "misconceptions_seed": [
                f"Assuming {chapter_title} can be learned without reading the chapter notes.",
            ],
            "applications_seed": [
                f"Applying {chapter_title} ideas in classroom and real-world examples.",
            ],
            "quiz_focus": [fact["term"] for fact in facts[:8]],
            "image_candidates": [],
        }
    }


def build_kaggle_artifacts(chapter_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    source = load_json_optional(chapter_root / "source" / "chapter_source.json")
    if not isinstance(source, dict):
        raise ValueError(f"missing source chapter json for {chapter_root}")

    chapter_title = str(source.get("chapter_title") or chapter_root.name)
    summary = summarize_source_text(source, chapter_title)
    key_points = {
        "chapter_title": chapter_title,
        "key_points": list(summary.get("key_points") or []),
    }

    notes_payload = build_chapter_notes(summary, [], chapter_title, source)
    notes = notes_payload.get("chapter_notes") if isinstance(notes_payload, dict) else {}
    facts = fact_bank_from_source(source, summary, chapter_title, notes if isinstance(notes, dict) else None)
    if len(facts) < 5:
        fallback_items = [clean_text(str(item)) for item in summary.get("key_points") or [] if clean_text(str(item))]
        for item in fallback_items:
            facts.append({"term": derive_term_from_fact(item, chapter_title), "fact": sentence_case(item), "source": "fallback_key_point"})
        facts = dedupe_by_key(facts, "term")

    concepts = make_concepts_from_facts(facts, limit=10)
    glossary = make_glossary_from_facts(facts, chapter_title, limit=12)
    misconceptions = make_misconceptions_from_facts(facts, chapter_title, limit=8)
    applications = make_applications_from_facts(facts, chapter_title, limit=8)
    flashcards = make_flashcards_from_facts(facts, limit=15)
    quizzes = make_quizzes_from_facts(facts, chapter_title, count=20)

    chapter_notes = build_chapter_notes(summary, facts, chapter_title, source)

    artifacts = {
        "summary.json": summary,
        "key_points.json": key_points,
        "concepts.json": concepts,
        "glossary.json": glossary,
        "misconceptions.json": misconceptions,
        "applications.json": applications,
        "flashcards.json": flashcards,
        "quizzes.json": quizzes,
        "chapter_notes.json": chapter_notes,
    }

    derived = {
        "facts": facts,
        "chapter_title": chapter_title,
        "source": source,
        "summary": summary,
        "key_points": key_points,
        "chapter_notes": chapter_notes,
    }
    return artifacts, derived


def build_pack_artifacts(chapter_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = load_json(chapter_root / "manifest.json")

    kaggle_artifacts, derived = build_kaggle_artifacts(chapter_root)
    source = derived["source"]
    chapter_title = derived["chapter_title"]
    summary = derived["summary"]
    key_points = derived["key_points"]
    facts = derived["facts"]
    concepts = kaggle_artifacts["concepts.json"]
    glossary = kaggle_artifacts["glossary.json"]
    misconceptions = kaggle_artifacts["misconceptions.json"]
    applications = kaggle_artifacts["applications.json"]
    flashcards = kaggle_artifacts["flashcards.json"]
    quizzes = kaggle_artifacts["quizzes.json"]

    sections = normalize_content_sections(source)
    content = sections
    summary_items = normalize_summary(summary, chapter_title)
    quiz_items = normalize_quizzes(facts, chapter_title)
    flashcard_items = normalize_flashcards(facts)
    concept_items = make_concepts_from_facts(facts, limit=10)
    glossary_items = make_glossary_from_facts(facts, chapter_title, limit=12)
    misconception_items = make_misconceptions_from_facts(facts, chapter_title, limit=8)
    application_items = make_applications_from_facts(facts, chapter_title, limit=8)
    chapter_notes = [
        {
            "title": chapter_title,
            "summary": summary_items[0]["text"] if summary_items else "",
            "key_points": summary_items[0].get("key_points", []) if summary_items else [],
        }
    ]

    textbook_payload = {
        "pack_id": chapter_pack_id(int(source.get("grade")) if source.get("grade") is not None else None, str(source.get("subject") or "unknown"), chapter_title),
        "title": chapter_title,
        "grade": source.get("grade"),
        "subject": source.get("subject"),
        "chapter": source.get("chapter_slug") or chapter_root.name,
        "language": "english",
        "sections": sections,
        "metadata": {
            "source": "kaggle_textbook_artifacts",
            "pdf_path": source.get("pdf_path"),
            "pdf_hash": source.get("pdf_hash"),
            "extractor": source.get("extractor"),
        },
    }

    retrieval_index = {
        item["chunk_id"]: {"title": item["title"], "text": item["text"][:1000], "metadata": item["metadata"]}
        for item in sections
    }

    artifacts = {
        "textbook": textbook_payload,
        "content": content,
        "chapter_notes": chapter_notes,
        "key_points": summary_items[0].get("key_points", []) if summary_items else [],
        "chapter_knowledge": {
            "summary": summary_items,
            "concepts": concept_items,
            "glossary": glossary_items,
            "misconceptions": misconception_items,
            "applications": application_items,
        },
        "concepts": concept_items,
        "examples": [],
        "worked_examples": [],
        "formulas": source.get("formulas") or [],
        "tutor_contexts": [],
        "activities": source.get("experiments") or [],
        "questions": [],
        "glossary": glossary_items,
        "misconceptions": misconception_items,
        "applications": application_items,
        "quizzes": quiz_items,
        "flashcards": flashcard_items,
        "summaries": summary_items,
        "enrichment": {
            "chapter_title": chapter_title,
            "source": "kaggle_textbook_artifacts",
            "grade": source.get("grade"),
            "subject": source.get("subject"),
            "fact_count": len(facts),
        },
        "retrieval_index": retrieval_index,
    }

    quality = chapter_quality_score(
        str(source.get("source_text") or ""),
        str(summary_items[0]["text"] if summary_items else ""),
        quiz_items,
        flashcard_items,
    )
    manifest_out = {
        "pack_id": textbook_payload["pack_id"],
        "version": "1.0.0",
        "grade": source.get("grade"),
        "subject": source.get("subject"),
        "chapter": source.get("chapter_slug") or chapter_root.name,
        "language": "english",
        "source_manifest": str(chapter_root / "manifest.json"),
        "source_pdf": source.get("pdf_path"),
        "source_pdf_hash": source.get("pdf_hash"),
        "chapter_title": chapter_title,
        "status": "imported",
        "quality": quality,
    }
    return artifacts, manifest_out


def write_kaggle_artifacts(chapter_root: Path, artifacts: dict[str, Any], dry_run: bool) -> list[str]:
    written: list[str] = []
    artifacts_root = chapter_root / "artifacts"
    for filename in EXPECTED_KAGGLE_ARTIFACTS:
        payload = artifacts.get(filename)
        if not dry_run:
            write_json_preserve(artifacts_root / filename, payload)
        written.append(filename)
    return written


def iter_chapters(root: Path, min_grade: int | None, max_grade: int | None) -> list[Path]:
    chapter_dirs: list[Path] = []
    for manifest_path in sorted(root.rglob("manifest.json")):
        chapter_root = manifest_path.parent
        source_path = chapter_root / "source" / "chapter_source.json"
        if not source_path.exists():
            continue
        try:
            manifest = load_json(manifest_path)
            source = load_json(source_path)
        except Exception:
            continue
        grade = source.get("grade")
        if grade is not None:
            try:
                grade_int = int(grade)
            except (TypeError, ValueError):
                grade_int = None
            if grade_int is not None:
                if min_grade is not None and grade_int < min_grade:
                    continue
                if max_grade is not None and grade_int > max_grade:
                    continue
        chapter_dirs.append(chapter_root)
    return chapter_dirs


def import_chapters(
    root: Path,
    storage_root: Path,
    replace_existing: bool,
    min_grade: int | None,
    max_grade: int | None,
    dry_run: bool,
    sync_packs: bool,
) -> dict[str, Any]:
    repository = PackRepository(storage_root) if sync_packs else None
    chapters = iter_chapters(root, min_grade=min_grade, max_grade=max_grade)
    report_rows: list[dict[str, Any]] = []

    for chapter_root in chapters:
        kaggle_artifacts, derived = build_kaggle_artifacts(chapter_root)
        written_files = write_kaggle_artifacts(chapter_root, kaggle_artifacts, dry_run=dry_run)
        artifacts, manifest = build_pack_artifacts(chapter_root)
        pack_id = str(manifest["pack_id"])
        grade = manifest.get("grade")
        subject = manifest.get("subject")
        chapter = manifest.get("chapter")
        excluded_runtime = is_runtime_excluded_chapter(str(chapter))

        if repository is not None and not excluded_runtime:
            if replace_existing and not dry_run:
                repository.remove_pack(pack_id)

            if not dry_run:
                repository.save_pack(
                    {
                        "pack_id": pack_id,
                        "version": "1.0.0",
                        "grade": grade,
                        "subject": subject,
                        "chapter": chapter,
                        "language": "english",
                        "artifacts": artifacts,
                        "generation_metadata": {
                            "source": "kaggle_textbook_artifacts",
                            "source_manifest": manifest["source_manifest"],
                            "source_pdf": manifest["source_pdf"],
                            "source_pdf_hash": manifest["source_pdf_hash"],
                            "chapter_title": manifest["chapter_title"],
                            "quality": manifest["quality"],
                        },
                        "quality_scores": {
                            "quality_score": manifest["quality"]["quality_score"],
                        },
                    }
                )

        report_rows.append(
            {
                "pack_id": pack_id,
                "grade": grade,
                "subject": subject,
                "chapter": chapter,
                "summary_chars": manifest["quality"]["summary_chars"],
                "quality_score": manifest["quality"]["quality_score"],
                "generic_quiz_count": manifest["quality"]["generic_quiz_count"],
                "generic_flashcard_count": manifest["quality"]["generic_flashcard_count"],
                "noise_flags": manifest["quality"]["noise_flags"],
                "written_files": written_files,
                "excluded_runtime": excluded_runtime,
                "dry_run": dry_run,
            }
        )

    quality_scores = [row["quality_score"] for row in report_rows]
    summary = {
        "chapter_count": len(report_rows),
        "average_quality_score": round(statistics.mean(quality_scores), 2) if quality_scores else 0.0,
        "median_quality_score": round(statistics.median(quality_scores), 2) if quality_scores else 0.0,
        "min_quality_score": min(quality_scores) if quality_scores else 0.0,
        "max_quality_score": max(quality_scores) if quality_scores else 0.0,
        "replace_existing": replace_existing,
        "dry_run": dry_run,
        "sync_packs": sync_packs,
        "storage_root": str(storage_root),
        "source_root": str(root),
        "excluded_runtime_chapters": sum(1 for row in report_rows if row.get("excluded_runtime")),
    }
    return {"summary": summary, "chapters": report_rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit and import Kaggle textbook artifacts into pack-service storage.")
    parser.add_argument("--root", default="textbook_artifacts", help="Root folder containing grade_* chapter outputs")
    parser.add_argument("--storage-root", default=str(Path("/tmp") / "pihub_textbook_pack_storage"), help="Pack service storage root")
    parser.add_argument("--min-grade", type=int, default=5)
    parser.add_argument("--max-grade", type=int, default=10)
    parser.add_argument("--replace-existing", action="store_true", help="Overwrite existing packs with the same pack_id")
    parser.add_argument("--sync-packs", action="store_true", help="Also publish derived packs into pack-service storage")
    parser.add_argument("--dry-run", action="store_true", help="Audit and report without writing pack storage")
    parser.add_argument("--output-dir", default=str(Path("/tmp") / "textbook_artifacts_import_report"), help="Where to write the report JSON")
    args = parser.parse_args()

    root = Path(args.root)
    storage_root = Path(args.storage_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    report = import_chapters(
        root=root,
        storage_root=storage_root,
        replace_existing=bool(args.replace_existing),
        min_grade=args.min_grade,
        max_grade=args.max_grade,
        dry_run=bool(args.dry_run),
        sync_packs=bool(args.sync_packs),
    )

    write_json(output_dir / "textbook_artifacts_import_report.json", report)
    print(json.dumps(report["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
