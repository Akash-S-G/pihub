#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import random
import re
import statistics
import tarfile
import urllib.request
from collections import Counter, defaultdict
from io import BytesIO
from pathlib import Path
from typing import Any


ARTIFACTS = ("summaries", "quizzes", "flashcards", "glossary")
TOPICS = ("arithmetic progression", "quadrilaterals", "gravitation", "constitutional design", "photosynthesis")
STOPWORDS = {
    "about", "above", "after", "again", "against", "also", "because", "been", "being", "between",
    "chapter", "could", "does", "during", "each", "from", "have", "into", "more", "most", "other",
    "should", "such", "than", "that", "their", "there", "these", "this", "those", "through", "under",
    "very", "were", "what", "when", "where", "which", "while", "with", "would", "your", "learn",
    "student", "students", "example", "examples", "concept", "concepts", "question", "answer",
}


def get_json(base_url: str, path: str, timeout: float) -> dict[str, Any]:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}{path}", timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def get_bytes(base_url: str, path: str, timeout: float) -> bytes:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}{path}", timeout=timeout) as response:
        return response.read()


def words(text: str) -> list[str]:
    return [word.lower() for word in re.findall(r"[A-Za-z][A-Za-z0-9'-]{2,}", text)]


def content_text(items: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for item in items:
        for key in ("text", "content", "body", "chunk", "summary"):
            value = item.get(key)
            if isinstance(value, str):
                parts.append(value)
    return "\n".join(parts)


def artifact_text(artifact_name: str, items: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    keys = {
        "summaries": ("title", "text", "topic"),
        "quizzes": ("question", "correct_answer", "explanation", "difficulty"),
        "flashcards": ("front", "back", "topic"),
        "glossary": ("term", "definition", "example"),
    }[artifact_name]
    for item in items:
        for key in keys:
            value = item.get(key)
            if isinstance(value, str):
                parts.append(value)
        if artifact_name == "quizzes":
            for option in item.get("options", []) or []:
                if isinstance(option, dict):
                    parts.append(str(option.get("text") or ""))
    return "\n".join(parts)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", value.lower())).strip()


def unique_ratio(values: list[str]) -> float:
    normalized = [normalize_text(value) for value in values if normalize_text(value)]
    if not normalized:
        return 1.0
    return len(set(normalized)) / len(normalized)


def keyword_set(text: str, limit: int = 80) -> set[str]:
    counts = Counter(word for word in words(text) if word not in STOPWORDS and len(word) > 3)
    return {word for word, _ in counts.most_common(limit)}


def supported_ratio(generated_text: str, source_keywords: set[str]) -> tuple[float, list[str]]:
    generated_keywords = keyword_set(generated_text, limit=120)
    if not generated_keywords:
        return 1.0, []
    unsupported = sorted(generated_keywords - source_keywords)[:20]
    return 1.0 - (len(generated_keywords - source_keywords) / len(generated_keywords)), unsupported


def readability_score(text: str) -> float:
    tokens = words(text)
    if not tokens:
        return 0.0
    sentences = max(1, len(re.findall(r"[.!?]+", text)))
    avg_sentence = len(tokens) / sentences
    avg_word = sum(len(token) for token in tokens) / len(tokens)
    sentence_score = max(0.0, 1.0 - abs(avg_sentence - 18.0) / 30.0)
    word_score = max(0.0, 1.0 - abs(avg_word - 5.2) / 5.0)
    return round(100.0 * (0.65 * sentence_score + 0.35 * word_score), 2)


def load_archive(payload: bytes) -> dict[str, Any]:
    result: dict[str, Any] = {}
    with tarfile.open(fileobj=BytesIO(payload), mode="r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            name = member.name.split("/", 1)[-1]
            if name in {"manifest.json", "content.json", "summaries.json", "quizzes.json", "flashcards.json", "glossary.json"}:
                file_obj = archive.extractfile(member)
                if file_obj is not None:
                    result[name] = json.loads(file_obj.read().decode("utf-8"))
    return result


def select_sample(packs: list[dict[str, Any]], target_count: int) -> list[dict[str, Any]]:
    by_subject: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pack in packs:
        subject = str(pack.get("subject") or "unknown").lower()
        by_subject[subject].append(pack)
    selected: list[dict[str, Any]] = []
    subjects = sorted(by_subject, key=lambda item: len(by_subject[item]), reverse=True)
    per_subject = max(1, math.ceil(target_count / max(5, min(len(subjects), 8))))
    random.seed(117)
    for subject in subjects:
        choices = sorted(by_subject[subject], key=lambda item: (str(item.get("grade")), str(item.get("pack_id"))))
        random.shuffle(choices)
        selected.extend(choices[:per_subject])
        if len(selected) >= target_count and len({str(item.get("subject")) for item in selected}) >= 5:
            break
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in selected:
        pack_id = str(item.get("pack_id"))
        if pack_id not in seen:
            unique.append(item)
            seen.add(pack_id)
    if len(unique) < target_count:
        for item in packs:
            pack_id = str(item.get("pack_id"))
            if pack_id not in seen:
                unique.append(item)
                seen.add(pack_id)
            if len(unique) >= target_count:
                break
    return unique[:target_count]


def score_pack(pack: dict[str, Any], archive: dict[str, Any]) -> dict[str, Any]:
    manifest = archive.get("manifest.json") or {}
    content = archive.get("content.json") or []
    source_text = content_text(content if isinstance(content, list) else [])
    source_keywords = keyword_set(source_text, limit=180)
    source_word_count = len(words(source_text))
    subject = str(pack.get("subject") or manifest.get("subject") or "unknown")
    chapter = str(pack.get("chapter") or manifest.get("chapter") or "")

    artifacts = {
        "summaries": archive.get("summaries.json") or [],
        "quizzes": archive.get("quizzes.json") or [],
        "flashcards": archive.get("flashcards.json") or [],
        "glossary": archive.get("glossary.json") or [],
    }
    artifact_scores: dict[str, Any] = {}
    all_generated_text = []

    summaries = artifacts["summaries"] if isinstance(artifacts["summaries"], list) else []
    summary_text = artifact_text("summaries", summaries)
    all_generated_text.append(summary_text)
    summary_support, summary_unsupported = supported_ratio(summary_text, source_keywords)
    summary_keywords = keyword_set(summary_text, limit=80)
    coverage = len(summary_keywords & source_keywords) / max(1, min(len(source_keywords), 80))
    artifact_scores["summaries"] = {
        "count": len(summaries),
        "coverage_score": round(coverage * 100, 2),
        "missing_concept_score": round((1.0 - coverage) * 100, 2),
        "hallucination_score": round((1.0 - summary_support) * 100, 2),
        "readability": readability_score(summary_text),
        "unsupported_terms": summary_unsupported[:10],
    }

    quizzes = artifacts["quizzes"] if isinstance(artifacts["quizzes"], list) else []
    quiz_text = artifact_text("quizzes", quizzes)
    all_generated_text.append(quiz_text)
    quiz_support, quiz_unsupported = supported_ratio(quiz_text, source_keywords)
    quiz_questions = [str(item.get("question") or "") for item in quizzes if isinstance(item, dict)]
    answer_support_scores = [
        supported_ratio(str(item.get("correct_answer") or ""), source_keywords)[0]
        for item in quizzes
        if isinstance(item, dict) and str(item.get("correct_answer") or "").strip()
    ]
    explanations = [str(item.get("explanation") or "") for item in quizzes if isinstance(item, dict)]
    distractor_counts = [len(item.get("options", []) or []) for item in quizzes if isinstance(item, dict)]
    artifact_scores["quizzes"] = {
        "count": len(quizzes),
        "answer_presence": round(100 * (len(answer_support_scores) / max(1, len(quizzes))), 2),
        "answer_source_support": round(100 * (statistics.mean(answer_support_scores) if answer_support_scores else 0.0), 2),
        "explanation_quality": round(100 * (sum(1 for value in explanations if len(words(value)) >= 8) / max(1, len(explanations))), 2),
        "distractor_quality": round(100 * (sum(1 for value in distractor_counts if value >= 4) / max(1, len(distractor_counts))), 2),
        "duplicate_question_rate": round(100 * (1 - unique_ratio(quiz_questions)), 2),
        "hallucination_score": round((1.0 - quiz_support) * 100, 2),
        "unsupported_terms": quiz_unsupported[:10],
    }

    flashcards = artifacts["flashcards"] if isinstance(artifacts["flashcards"], list) else []
    flash_text = artifact_text("flashcards", flashcards)
    all_generated_text.append(flash_text)
    flash_support, flash_unsupported = supported_ratio(flash_text, source_keywords)
    flash_fronts = [str(item.get("front") or "") for item in flashcards if isinstance(item, dict)]
    trivial = [
        len(words(str(item.get("front") or ""))) <= 3 or len(words(str(item.get("back") or ""))) <= 5
        for item in flashcards
        if isinstance(item, dict)
    ]
    artifact_scores["flashcards"] = {
        "count": len(flashcards),
        "concept_coverage": round(100 * len(keyword_set(flash_text, limit=80) & source_keywords) / max(1, min(len(source_keywords), 80)), 2),
        "redundancy_score": round(100 * (1 - unique_ratio(flash_fronts)), 2),
        "triviality_score": round(100 * (sum(trivial) / max(1, len(trivial))), 2),
        "hallucination_score": round((1.0 - flash_support) * 100, 2),
        "unsupported_terms": flash_unsupported[:10],
    }

    glossary = artifacts["glossary"] if isinstance(artifacts["glossary"], list) else []
    glossary_text = artifact_text("glossary", glossary)
    all_generated_text.append(glossary_text)
    glossary_support, glossary_unsupported = supported_ratio(glossary_text, source_keywords)
    terms = [str(item.get("term") or "") for item in glossary if isinstance(item, dict)]
    definitions = [str(item.get("definition") or "") for item in glossary if isinstance(item, dict)]
    critical_keywords = {word for word, _ in Counter(word for word in words(source_text) if word not in STOPWORDS and len(word) > 5).most_common(20)}
    glossary_terms = keyword_set(" ".join(terms), limit=60)
    missing_critical = sorted(critical_keywords - glossary_terms)[:10]
    artifact_scores["glossary"] = {
        "count": len(glossary),
        "term_extraction_quality": round(100 * len(glossary_terms & source_keywords) / max(1, len(glossary_terms)), 2),
        "definition_quality": round(100 * (sum(1 for value in definitions if len(words(value)) >= 7) / max(1, len(definitions))), 2),
        "missing_critical_terms": missing_critical,
        "hallucination_score": round((1.0 - glossary_support) * 100, 2),
        "unsupported_terms": glossary_unsupported[:10],
    }

    generated_text = "\n".join(all_generated_text)
    support, unsupported = supported_ratio(generated_text, source_keywords)
    completeness = min(100.0, 100.0 * len(keyword_set(generated_text, limit=160) & source_keywords) / max(1, min(len(source_keywords), 160)))
    usefulness = min(100.0, 8.0 * len(summaries) + 4.0 * len(quizzes) + 2.0 * len(flashcards) + 2.0 * len(glossary))
    duplication = 100.0 - statistics.mean([
        artifact_scores["quizzes"]["duplicate_question_rate"],
        artifact_scores["flashcards"]["redundancy_score"],
    ])
    readability = readability_score(generated_text)
    alignment_terms = [subject, chapter]
    alignment_hits = sum(1 for value in alignment_terms if value and value.lower() in generated_text.lower())
    curriculum_alignment = 60.0 + (20.0 * alignment_hits) if source_word_count else 0.0
    overall = statistics.mean([
        support * 100.0,
        completeness,
        usefulness,
        duplication,
        readability,
        min(100.0, curriculum_alignment),
    ])
    return {
        "pack_id": pack.get("pack_id"),
        "grade": pack.get("grade"),
        "subject": subject,
        "chapter": chapter,
        "source_word_count": source_word_count,
        "artifact_scores": artifact_scores,
        "overall_quality_score": round(overall, 2),
        "factual_accuracy_proxy": round(support * 100.0, 2),
        "educational_usefulness": round(usefulness, 2),
        "completeness": round(completeness, 2),
        "duplication_quality": round(duplication, 2),
        "hallucination_rate_proxy": round((1.0 - support) * 100.0, 2),
        "readability": readability,
        "curriculum_alignment": round(min(100.0, curriculum_alignment), 2),
        "unsupported_terms": unsupported[:15],
        "missing_concepts": sorted((source_keywords - keyword_set(generated_text, limit=160)))[:15],
        "samples": {
            "summary": summaries[:1],
            "quiz": quizzes[:1],
            "flashcard": flashcards[:1],
            "glossary": glossary[:1],
        },
    }


def topic_readiness(topic: str, pack_scores: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [
        score for score in pack_scores
        if topic.lower() in f"{score.get('pack_id')} {score.get('chapter')} {score.get('subject')}".lower()
    ]
    if not candidates:
        keyword = topic.split()[0].lower()
        candidates = [
            score for score in pack_scores
            if keyword in f"{score.get('pack_id')} {score.get('chapter')} {score.get('subject')}".lower()
        ]
    if not candidates:
        return {"topic": topic, "rating": 0.0, "evidence": "No sampled pack matched topic.", "pack_count": 0}
    rating = statistics.mean(score["overall_quality_score"] for score in candidates)
    return {
        "topic": topic,
        "rating": round(rating, 2),
        "pack_count": len(candidates),
        "sample_pack_ids": [score["pack_id"] for score in candidates[:5]],
    }


def write_report(output_dir: Path, output: dict[str, Any]) -> None:
    summary = output["summary"]
    subject_rows = [
        [subject, data["pack_count"], data["overall_quality_score"], data["factual_accuracy_proxy"], data["hallucination_rate_proxy"], data["completeness"]]
        for subject, data in sorted(output["subject_scores"].items())
    ]
    defect_rows = [
        [item["pack_id"], item["subject"], item["chapter"], item["overall_quality_score"], item["hallucination_rate_proxy"], ", ".join(item["unsupported_terms"][:6])]
        for item in output["bottom_packs"][:20]
    ]
    readiness_rows = [
        [item["topic"], item["rating"], item["pack_count"], ", ".join(map(str, item.get("sample_pack_ids", []))) or item.get("evidence", "")]
        for item in output["tutor_readiness"]
    ]
    hallucination_examples = []
    missing_examples = []
    for score in output["pack_scores"]:
        if score["unsupported_terms"]:
            hallucination_examples.append([score["pack_id"], score["subject"], score["chapter"], ", ".join(score["unsupported_terms"][:8])])
        if score["missing_concepts"]:
            missing_examples.append([score["pack_id"], score["subject"], score["chapter"], ", ".join(score["missing_concepts"][:8])])

    report = "\n".join([
        "# AI Content Generation Quality Audit",
        "",
        "## Scope",
        "",
        f"Sampled packs: {summary['sampled_packs']}",
        f"Subjects sampled: {', '.join(summary['subjects_sampled'])}",
        f"Grades sampled: {', '.join(map(str, summary['grades_sampled']))}",
        "Artifacts audited: summaries.json, quizzes.json, flashcards.json, glossary.json",
        "",
        f"Full runtime catalog subject labels: {json.dumps(output['catalog_subject_distribution'], ensure_ascii=False, sort_keys=True)}",
        "Catalog limitation: the runtime sync catalog exposes 4 distinct subject labels, so a 5-subject sample is not possible from current backend metadata.",
        "",
        "Scoring note: factual accuracy and hallucination are proxy measurements based on whether generated artifact concepts are supported by the pack's source `content.json`. This is evidence-based but not a substitute for human curriculum review.",
        "",
        "## Overall Scores",
        "",
        f"Overall quality score: {summary['overall_quality_score']}",
        f"Factual accuracy proxy: {summary['factual_accuracy_proxy']}",
        f"Educational usefulness: {summary['educational_usefulness']}",
        f"Completeness: {summary['completeness']}",
        f"Duplication quality: {summary['duplication_quality']}",
        f"Hallucination rate proxy: {summary['hallucination_rate_proxy']}",
        f"Readability: {summary['readability']}",
        f"Curriculum alignment: {summary['curriculum_alignment']}",
        f"Tutor readiness rating: {summary['tutor_readiness_rating']}",
        "",
        "## Subject-Wise Scores",
        "",
        markdown_table(["Subject", "Packs", "Overall", "Factual Proxy", "Hallucination Proxy", "Completeness"], subject_rows),
        "",
        "## Tutor Readiness",
        "",
        markdown_table(["Topic", "Readiness", "Matched Packs", "Evidence"], readiness_rows),
        "",
        "## Top Defects",
        "",
        markdown_table(["pack_id", "subject", "chapter", "quality", "hallucination_proxy", "unsupported_terms"], defect_rows),
        "",
        "## Top Strengths",
        "",
        markdown_table(["pack_id", "subject", "chapter", "quality", "factual_proxy", "completeness"], [[item["pack_id"], item["subject"], item["chapter"], item["overall_quality_score"], item["factual_accuracy_proxy"], item["completeness"]] for item in output["top_packs"][:20]]),
        "",
        "## Hallucination Examples",
        "",
        markdown_table(["pack_id", "subject", "chapter", "unsupported artifact terms"], hallucination_examples[:20]),
        "",
        "## Missing Concept Examples",
        "",
        markdown_table(["pack_id", "subject", "chapter", "source concepts not covered by artifacts"], missing_examples[:20]),
        "",
        "## Artifact-Level Averages",
        "",
        "```json",
        json.dumps(output["artifact_averages"], indent=2, ensure_ascii=False, sort_keys=True),
        "```",
        "",
        "## Evidence Classification",
        "",
        "- FACT: Artifact files were downloaded from runtime pack archives and parsed directly.",
        "- FACT: Duplicate, count, readability, and source-support metrics are computed from sampled archive data.",
        "- LIKELY: Unsupported artifact keywords indicate hallucination or unsupported generation when they do not appear in source content.",
        "- UNPROVEN: Full factual correctness against official textbooks requires manual expert review beyond this automated audit.",
    ])
    output_dir.joinpath("AI_CONTENT_GENERATION_QUALITY_AUDIT_REPORT.md").write_text(report, encoding="utf-8")


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit generated AI content artifacts in PIHUB runtime packs.")
    parser.add_argument("--base-url", default="http://localhost")
    parser.add_argument("--sample-size", type=int, default=50)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    sync = get_json(args.base_url, "/packs/sync", args.timeout)
    packs = sync.get("packs", [])
    catalog_subject_distribution = Counter(str(pack.get("subject") or "unknown") for pack in packs)
    sample = select_sample(packs, args.sample_size)
    pack_scores: list[dict[str, Any]] = []
    for pack in sample:
        payload = get_bytes(args.base_url, str(pack.get("download_url")), args.timeout)
        archive = load_archive(payload)
        pack_scores.append(score_pack(pack, archive))

    numeric_keys = (
        "overall_quality_score",
        "factual_accuracy_proxy",
        "educational_usefulness",
        "completeness",
        "duplication_quality",
        "hallucination_rate_proxy",
        "readability",
        "curriculum_alignment",
    )
    subject_scores: dict[str, dict[str, Any]] = {}
    for subject in sorted({score["subject"] for score in pack_scores}):
        group = [score for score in pack_scores if score["subject"] == subject]
        subject_scores[subject] = {
            "pack_count": len(group),
            **{key: round(statistics.mean(score[key] for score in group), 2) for key in numeric_keys},
        }

    artifact_averages: dict[str, dict[str, float]] = {}
    for artifact in ARTIFACTS:
        metric_values: dict[str, list[float]] = defaultdict(list)
        for score in pack_scores:
            for key, value in score["artifact_scores"][artifact].items():
                if isinstance(value, (int, float)):
                    metric_values[key].append(float(value))
        artifact_averages[artifact] = {key: round(statistics.mean(values), 2) for key, values in metric_values.items()}

    readiness = [topic_readiness(topic, pack_scores) for topic in TOPICS]
    readiness_rating = round(statistics.mean(item["rating"] for item in readiness), 2)
    output = {
        "summary": {
            "sampled_packs": len(pack_scores),
            "subjects_sampled": sorted({score["subject"] for score in pack_scores}),
            "grades_sampled": sorted({score["grade"] for score in pack_scores if score.get("grade") is not None}),
            **{key: round(statistics.mean(score[key] for score in pack_scores), 2) for key in numeric_keys},
            "tutor_readiness_rating": readiness_rating,
        },
        "subject_scores": subject_scores,
        "artifact_averages": artifact_averages,
        "tutor_readiness": readiness,
        "catalog_subject_distribution": dict(sorted(catalog_subject_distribution.items())),
        "top_packs": sorted(pack_scores, key=lambda item: item["overall_quality_score"], reverse=True),
        "bottom_packs": sorted(pack_scores, key=lambda item: item["overall_quality_score"]),
        "pack_scores": pack_scores,
    }
    output_dir.joinpath("ai_content_generation_quality_audit.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    write_report(output_dir, output)
    print(json.dumps(output["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
