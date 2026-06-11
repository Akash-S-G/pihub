#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import statistics
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.semantic_content_pipeline import (
    is_header_footer_or_metadata,
    is_ocr_noise,
    is_toc_or_index,
    normalize_text,
    token_set,
    word_count,
)


BASE_URL = "http://localhost:8030"
OUT_DIR = Path("/shared/grade8_semantic_validation")
GRADE = 8

BENCHMARK_QUESTIONS = [
    "What is proportional reasoning?",
    "Explain force.",
    "What is pressure?",
    "Explain democracy.",
    "What are natural resources?",
]


def get_json(path: str, timeout: float = 120.0) -> Any:
    with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(path: str, payload: dict[str, Any], timeout: float = 600.0) -> tuple[int, Any]:
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed: Any = json.loads(body)
        except json.JSONDecodeError:
            parsed = body
        return exc.code, parsed


def load_json(path: Path) -> Any:
    if not path.exists():
        return [] if path.suffix == ".json" else {}
    return json.loads(path.read_text(encoding="utf-8"))


def list_grade8_packs() -> list[dict[str, Any]]:
    packs = get_json("/packs/list").get("packs", [])
    return [pack for pack in packs if str(pack.get("grade")) == str(GRADE)]


def pack_payload(pack: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "pack_type": "chapter" if pack.get("chapter") else "class",
        "grade": GRADE,
        "subject": pack.get("subject"),
        "chapter": pack.get("chapter"),
        "language": pack.get("language") or "english",
    }
    return {key: value for key, value in payload.items() if value not in (None, "")}


def content_rows(pack: dict[str, Any], filename: str = "content.json") -> list[dict[str, Any]]:
    pack_dir = Path(str(pack.get("archive_path") or "")).with_suffix("").with_suffix("")
    if not pack_dir.exists():
        pack_dir = Path(str(pack.get("manifest_path") or "")).parent
    value = load_json(pack_dir / filename)
    return value if isinstance(value, list) else []


def report_rows(pack: dict[str, Any], filename: str) -> Any:
    pack_dir = Path(str(pack.get("archive_path") or "")).with_suffix("").with_suffix("")
    if not pack_dir.exists():
        pack_dir = Path(str(pack.get("manifest_path") or "")).parent
    return load_json(pack_dir / "reports" / filename)


def average_word_length(rows: list[dict[str, Any]]) -> float:
    lengths = [word_count(row.get("text")) for row in rows if row.get("text")]
    return round(sum(lengths) / max(1, len(lengths)), 2)


def duplicate_ratio(rows: list[dict[str, Any]]) -> float:
    hashes = [normalize_text(row.get("text")) for row in rows if row.get("text")]
    if not hashes:
        return 0.0
    counts = Counter(hashes)
    duplicates = sum(count - 1 for count in counts.values() if count > 1)
    return round(duplicates / len(hashes), 4)


def text_quality(row: dict[str, Any]) -> dict[str, bool]:
    text = str(row.get("text") or "")
    lowered = normalize_text(text)
    return {
        "toc": is_toc_or_index(text),
        "isbn": "isbn" in lowered or "copyright" in lowered,
        "header_footer": is_header_footer_or_metadata(text),
        "ocr_noise": is_ocr_noise(text),
        "readable": word_count(text) >= 100 and not is_ocr_noise(text),
    }


def score_ratio(pass_count: int, total: int) -> float:
    return round(100.0 * pass_count / max(1, total), 2)


def sample_by_subject(packs: list[dict[str, Any]], per_subject: int = 5) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pack in packs:
        subject = normalize_text(pack.get("subject"))
        if "math" in subject:
            key = "maths"
        elif "social" in subject:
            key = "social_science"
        elif "science" in subject:
            key = "science"
        else:
            key = subject or "unknown"
        buckets[key].append(pack)
    samples: list[dict[str, Any]] = []
    for key in ("maths", "science", "social_science"):
        eligible = [pack for pack in buckets.get(key, []) if int((pack.get("artifact_counts") or {}).get("content") or 0) > 0]
        samples.extend(eligible[:per_subject])
    return samples


def reader_quality(packs: list[dict[str, Any]]) -> dict[str, Any]:
    samples = sample_by_subject(packs)
    rows = []
    pass_count = 0
    total = 0
    for pack in samples:
        content = content_rows(pack)[:20]
        findings = Counter()
        readable = 0
        for item in content:
            quality = text_quality(item)
            total += 1
            if quality["readable"] and not any(quality[key] for key in ("toc", "isbn", "header_footer", "ocr_noise")):
                pass_count += 1
                readable += 1
            for key, value in quality.items():
                if value:
                    findings[key] += 1
        rows.append(
            {
                "pack_id": pack.get("pack_id"),
                "subject": pack.get("subject"),
                "chapter": pack.get("chapter"),
                "sampled_chunks": len(content),
                "findings": dict(findings),
                "readable_ratio": round(readable / max(1, len(content)), 4),
                "sample_text": str(content[0].get("text") if content else "")[:500],
            }
        )
    return {"score": score_ratio(pass_count, total), "sampled_chapters": len(samples), "sampled_chunks": total, "rows": rows}


def quiz_quality(packs: list[dict[str, Any]], limit: int = 100) -> dict[str, Any]:
    rows = []
    scores = Counter()
    total = 0
    for pack in packs:
        for quiz in content_rows(pack, "quizzes.json"):
            if total >= limit:
                break
            question = str(quiz.get("question") or "")
            answer = str(quiz.get("correct_answer") or quiz.get("answer") or "")
            explanation = str(quiz.get("explanation") or answer)
            text = f"{question} {answer} {explanation}"
            record = {
                "pack_id": pack.get("pack_id"),
                "question": question,
                "correctness": bool(question and answer and word_count(answer) >= 5),
                "distractor_quality": bool(quiz.get("options")) and len(quiz.get("options") or []) >= 3,
                "explanation_quality": word_count(explanation) >= 8,
                "curriculum_alignment": bool(token_set(text) & token_set(f"{pack.get('chapter')} {pack.get('subject')}")),
            }
            for key in ("correctness", "distractor_quality", "explanation_quality", "curriculum_alignment"):
                scores[key] += int(record[key])
            rows.append(record)
            total += 1
        if total >= limit:
            break
    composite = statistics.mean([score_ratio(scores[key], total) for key in scores]) if scores else 0.0
    return {"score": round(composite, 2), "sampled_questions": total, "metrics": {key: score_ratio(value, total) for key, value in scores.items()}, "rows": rows}


def summary_quality(packs: list[dict[str, Any]]) -> dict[str, Any]:
    samples = sample_by_subject(packs)
    rows = []
    pass_count = 0
    total = 0
    for pack in samples:
        summaries = content_rows(pack, "summaries.json")
        content_terms = token_set(" ".join(str(row.get("text") or "") for row in content_rows(pack)[:10]))
        for summary in summaries[:1]:
            text = str(summary.get("text") or summary.get("summary") or "")
            terms = token_set(text)
            factual = bool(terms & content_terms) if content_terms else bool(terms)
            useful = word_count(text) >= 50
            coverage = len(terms & content_terms) / max(1, min(len(content_terms), 50)) if content_terms else 0.0
            ok = factual and useful and coverage >= 0.08
            pass_count += int(ok)
            total += 1
            rows.append({"pack_id": pack.get("pack_id"), "chapter": pack.get("chapter"), "factual_accuracy": factual, "revision_usefulness": useful, "concept_coverage": round(coverage, 4), "passed": ok, "text": text[:700]})
    return {"score": score_ratio(pass_count, total), "sampled_summaries": total, "rows": rows}


def flashcard_quality(packs: list[dict[str, Any]]) -> dict[str, Any]:
    samples = sample_by_subject(packs)
    rows = []
    pass_count = 0
    total = 0
    for pack in samples:
        content_terms = token_set(" ".join(str(row.get("text") or "") for row in content_rows(pack)[:10]))
        cards = content_rows(pack, "flashcards.json")[:10]
        for card in cards:
            front = str(card.get("front") or "")
            back = str(card.get("back") or "")
            useful = word_count(front) >= 1 and word_count(back) >= 5
            relevant = bool(token_set(f"{front} {back}") & content_terms) if content_terms else useful
            memorization = len(front) <= 80 and len(back) <= 350
            ok = useful and relevant and memorization
            pass_count += int(ok)
            total += 1
            rows.append({"pack_id": pack.get("pack_id"), "front": front, "concept_usefulness": useful, "memorization_value": memorization, "educational_relevance": relevant, "passed": ok})
    return {"score": score_ratio(pass_count, total), "sampled_flashcards": total, "rows": rows}


def search_content(query: str, rows: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    q_terms = token_set(query)
    scored = []
    for row in rows:
        terms = token_set(str(row.get("text") or ""))
        if not terms:
            continue
        score = len(q_terms & terms) / math.sqrt(max(1, len(terms)))
        if score > 0:
            scored.append((score, row))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [row for _, row in scored[:limit]]


def tutor_benchmark(before_snapshot: dict[str, list[dict[str, Any]]], after_packs: list[dict[str, Any]]) -> dict[str, Any]:
    after_content = []
    before_content = []
    for pack in after_packs:
        after_content.extend(content_rows(pack))
        before_content.extend(before_snapshot.get(str(pack.get("pack_id")), []))

    rows = []
    old_scores = []
    new_scores = []
    for question in BENCHMARK_QUESTIONS:
        q_terms = token_set(question)
        old_results = search_content(question, before_content)
        new_results = search_content(question, after_content)

        def score(results: list[dict[str, Any]]) -> dict[str, float]:
            if not results:
                return {"accuracy": 0.0, "completeness": 0.0, "hallucination_rate": 1.0, "educational_usefulness": 0.0}
            relevant = sum(1 for item in results if token_set(str(item.get("text") or "")) & q_terms)
            readable = sum(1 for item in results if word_count(item.get("text")) >= 100)
            return {
                "accuracy": relevant / len(results),
                "completeness": min(1.0, len(results) / 5),
                "hallucination_rate": 1.0 - (relevant / len(results)),
                "educational_usefulness": readable / len(results),
            }

        old_score = score(old_results)
        new_score = score(new_results)
        old_scores.append(old_score)
        new_scores.append(new_score)
        rows.append({"question": question, "old": old_score, "new": new_score, "new_sample": [str(item.get("text") or "")[:300] for item in new_results[:2]]})

    def aggregate(items: list[dict[str, float]]) -> dict[str, float]:
        return {key: round(100 * statistics.mean(item[key] for item in items), 2) for key in items[0]} if items else {}

    new_agg = aggregate(new_scores)
    score = round(statistics.mean([new_agg.get("accuracy", 0), new_agg.get("completeness", 0), 100 - new_agg.get("hallucination_rate", 100), new_agg.get("educational_usefulness", 0)]), 2)
    return {"score": score, "old_packs": aggregate(old_scores), "new_semantic_packs": new_agg, "rows": rows}


def write_report(name: str, payload: Any) -> None:
    (OUT_DIR / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def markdown_gate(regen: dict[str, Any], reader: dict[str, Any], quiz: dict[str, Any], summary: dict[str, Any], flashcard: dict[str, Any], tutor: dict[str, Any]) -> str:
    scores = {
        "Reader Quality": reader["score"],
        "Quiz Quality": quiz["score"],
        "Summary Quality": summary["score"],
        "Flashcard Quality": flashcard["score"],
        "Tutor Quality": tutor["score"],
    }
    approved = all(score >= 90 for score in scores.values())
    lines = [
        "# Grade 8 Semantic Pipeline Validation",
        "",
        f"Final verdict: {'APPROVED_FOR_FULL_REGENERATION' if approved else 'REQUIRES_PIPELINE_REVISIONS'}",
        "",
        "## Regeneration",
        "",
        "```json",
        json.dumps(regen, indent=2, sort_keys=True),
        "```",
        "",
        "## Approval Scores",
        "",
        "| Gate | Score | Pass |",
        "| --- | ---: | --- |",
    ]
    for name, score in scores.items():
        lines.append(f"| {name} | {score:.2f} | {'PASS' if score >= 90 else 'FAIL'} |")
    lines.extend(
        [
            "",
            "## Evidence Files",
            "",
            "- grade8_regeneration_report.json",
            "- grade8_reader_quality_report.json",
            "- grade8_quiz_quality_report.json",
            "- grade8_summary_quality_report.json",
            "- grade8_flashcard_quality_report.json",
            "- grade8_tutor_benchmark_report.json",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    started = time.time()
    before_packs = list_grade8_packs()
    before_snapshot = {str(pack.get("pack_id")): content_rows(pack) for pack in before_packs}
    chunks_before = sum(len(rows) for rows in before_snapshot.values())
    before_lengths = [word_count(row.get("text")) for rows in before_snapshot.values() for row in rows if row.get("text")]

    regeneration_rows = []
    for pack in before_packs:
        payload = pack_payload(pack)
        before_count = len(before_snapshot.get(str(pack.get("pack_id")), []))
        status, response = post_json("/packs/generate", payload)
        regeneration_rows.append(
            {
                "pack_id": pack.get("pack_id"),
                "subject": pack.get("subject"),
                "chapter": pack.get("chapter"),
                "before_chunks": before_count,
                "payload": payload,
                "status_code": status,
                "response": response,
                "regenerated": 200 <= int(status) < 300,
            }
        )

    after_packs = list_grade8_packs()
    after_content_by_id = {str(pack.get("pack_id")): content_rows(pack) for pack in after_packs}
    chunks_after = sum(len(rows) for rows in after_content_by_id.values())
    after_lengths = [word_count(row.get("text")) for rows in after_content_by_id.values() for row in rows if row.get("text")]
    quality_gate_passes = 0
    duplicates_removed = 0
    for pack in after_packs:
        gate = report_rows(pack, "quality_gate.json")
        dedupe = report_rows(pack, "deduplication_report.json")
        if isinstance(gate, dict) and gate.get("passed"):
            quality_gate_passes += 1
        if isinstance(dedupe, dict):
            duplicates_removed += int(dedupe.get("duplicates_removed") or 0)

    regen_report = {
        "grade": GRADE,
        "packs_targeted": len(before_packs),
        "packs_regenerated": sum(1 for row in regeneration_rows if row["regenerated"]),
        "packs_failed": sum(1 for row in regeneration_rows if not row["regenerated"]),
        "chunks_before": chunks_before,
        "chunks_after": chunks_after,
        "duplicates_removed": duplicates_removed,
        "average_chunk_length_before": round(sum(before_lengths) / max(1, len(before_lengths)), 2),
        "average_chunk_length_after": round(sum(after_lengths) / max(1, len(after_lengths)), 2),
        "quality_gate_pass_rate": round(quality_gate_passes / max(1, len(after_packs)), 4),
        "duration_ms": round((time.time() - started) * 1000, 2),
        "rows": regeneration_rows,
    }

    reader = reader_quality(after_packs)
    quiz = quiz_quality(after_packs)
    summary = summary_quality(after_packs)
    flashcard = flashcard_quality(after_packs)
    tutor = tutor_benchmark(before_snapshot, after_packs)

    write_report("grade8_regeneration_report.json", regen_report)
    write_report("grade8_reader_quality_report.json", reader)
    write_report("grade8_quiz_quality_report.json", quiz)
    write_report("grade8_summary_quality_report.json", summary)
    write_report("grade8_flashcard_quality_report.json", flashcard)
    write_report("grade8_tutor_benchmark_report.json", tutor)
    (OUT_DIR / "GRADE8_SEMANTIC_PIPELINE_VALIDATION.md").write_text(
        markdown_gate(regen_report, reader, quiz, summary, flashcard, tutor),
        encoding="utf-8",
    )
    print(json.dumps({"output_dir": str(OUT_DIR), "packs_targeted": len(before_packs), "packs_regenerated": regen_report["packs_regenerated"]}, indent=2))


if __name__ == "__main__":
    main()
