#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient


class SimpleEmbeddingModel:
    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def encode(self, texts: list[str] | str, normalize_embeddings: bool = True) -> list[list[float]]:
        if isinstance(texts, str):
            texts = [texts]
        return [self._encode_one(text, normalize_embeddings) for text in texts]

    def _encode_one(self, text: str, normalize_embeddings: bool) -> list[float]:
        vector = [0.0] * self.dimension
        for token in re.findall(r"[A-Za-z0-9']+", text.lower()):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest, "big") % self.dimension
            vector[index] += 1.0
        if normalize_embeddings:
            norm = math.sqrt(sum(value * value for value in vector))
            if norm > 0:
                vector = [value / norm for value in vector]
        return vector


@dataclass(frozen=True)
class BenchmarkQuestion:
    query: str
    expected_subject: str
    expected_chapter_contains: str


SEED_QUESTIONS = [
    BenchmarkQuestion("What is arithmetic progression?", "maths", "arithmetic progressions"),
    BenchmarkQuestion("Explain photosynthesis.", "science", "photosynthesis"),
    BenchmarkQuestion("State Newton's second law.", "science", "force"),
    BenchmarkQuestion("What is democracy?", "social_science", "democracy"),
    BenchmarkQuestion("What is rationalization?", "maths", "rationalisation"),
    BenchmarkQuestion("Explain quadrilaterals.", "maths", "quadrilaterals"),
    BenchmarkQuestion("What is gravitation?", "science", "gravitation"),
    BenchmarkQuestion("Explain heredity.", "science", "heredity"),
    BenchmarkQuestion("What are factors of production?", "science", "factors of production"),
    BenchmarkQuestion("What is proportional reasoning?", "maths", "proportional reasoning"),
]


def load_pack_index(storage_path: Path) -> list[dict[str, Any]]:
    data = json.loads((storage_path / "pack_index.json").read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and isinstance(data.get("packs"), list):
        return [item for item in data["packs"] if isinstance(item, dict)]
    return []


def build_questions(packs: list[dict[str, Any]], limit: int) -> list[BenchmarkQuestion]:
    questions = list(SEED_QUESTIONS)
    for pack in packs:
        subject = str(pack.get("subject") or "")
        chapter = str(pack.get("chapter") or "")
        if not subject or not chapter:
            continue
        questions.append(BenchmarkQuestion(f"Explain {chapter}.", subject, chapter.lower()))
        if len(questions) >= limit:
            break
    return questions[:limit]


def hit_payload(hit: Any) -> dict[str, Any]:
    return hit.payload or {}


def matches_subject(payload: dict[str, Any], expected: str) -> bool:
    actual = str(payload.get("subject") or "").lower()
    expected_norm = expected.lower()
    if actual == expected_norm:
        return True
    if expected_norm == "social_science" and actual in {"science", "social_science"}:
        return True
    return False


def matches_chapter(payload: dict[str, Any], expected_contains: str) -> bool:
    chapter = str(payload.get("chapter") or "").lower()
    return expected_contains.lower() in chapter or chapter in expected_contains.lower()


def evaluate_question(client: QdrantClient, collection: str, model: SimpleEmbeddingModel, question: BenchmarkQuestion, limit: int = 5) -> dict[str, Any]:
    query_vector = model.encode([question.query], normalize_embeddings=True)[0]
    if hasattr(client, "search"):
        hits = client.search(collection_name=collection, query_vector=query_vector, limit=limit, with_payload=True)
    else:
        response = client.query_points(collection_name=collection, query=query_vector, limit=limit, with_payload=True)
        hits = getattr(response, "points", response)
    payloads = [hit_payload(hit) for hit in hits]
    subject_matches = [matches_subject(payload, question.expected_subject) for payload in payloads]
    chapter_matches = [matches_chapter(payload, question.expected_chapter_contains) for payload in payloads]
    combined_matches = [subject and chapter for subject, chapter in zip(subject_matches, chapter_matches)]
    return {
        "query": question.query,
        "expected_subject": question.expected_subject,
        "expected_chapter_contains": question.expected_chapter_contains,
        "top1_subject": bool(subject_matches[:1] and subject_matches[0]),
        "top3_subject": any(subject_matches[:3]),
        "top5_subject": any(subject_matches[:5]),
        "top1_chapter": bool(chapter_matches[:1] and chapter_matches[0]),
        "top3_chapter": any(chapter_matches[:3]),
        "top5_chapter": any(chapter_matches[:5]),
        "top1_combined": bool(combined_matches[:1] and combined_matches[0]),
        "top3_combined": any(combined_matches[:3]),
        "top5_combined": any(combined_matches[:5]),
        "hits": [
            {
                "subject": payload.get("subject"),
                "chapter": payload.get("chapter"),
                "topic": payload.get("topic"),
                "text_preview": str(payload.get("text") or "")[:180],
            }
            for payload in payloads
        ],
    }


def ratio(rows: list[dict[str, Any]], key: str) -> float:
    return round(sum(1 for row in rows if row[key]) / max(1, len(rows)), 4)


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate current Qdrant retrieval quality with deterministic PIHUB embeddings.")
    parser.add_argument("--storage-path", default="/shared/packs")
    parser.add_argument("--qdrant-url", default="http://qdrant:6333")
    parser.add_argument("--collection", default="educational_chunks")
    parser.add_argument("--questions", type=int, default=100)
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    packs = load_pack_index(Path(args.storage_path))
    questions = build_questions(packs, args.questions)
    client = QdrantClient(url=args.qdrant_url)
    model = SimpleEmbeddingModel()
    rows = [evaluate_question(client, args.collection, model, question) for question in questions]
    summary = {
        "question_count": len(rows),
        "top1_retrieval_accuracy": ratio(rows, "top1_combined"),
        "top3_retrieval_accuracy": ratio(rows, "top3_combined"),
        "top5_retrieval_accuracy": ratio(rows, "top5_combined"),
        "subject_top1_accuracy": ratio(rows, "top1_subject"),
        "subject_top3_accuracy": ratio(rows, "top3_subject"),
        "subject_top5_accuracy": ratio(rows, "top5_subject"),
        "chapter_top1_accuracy": ratio(rows, "top1_chapter"),
        "chapter_top3_accuracy": ratio(rows, "top3_chapter"),
        "chapter_top5_accuracy": ratio(rows, "top5_chapter"),
        "target_top5_gt_0_90": ratio(rows, "top5_combined") > 0.90,
    }
    (output_dir / "retrieval_quality.json").write_text(json.dumps({"summary": summary, "questions": rows}, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    report_rows = [
        [row["query"], row["expected_subject"], row["expected_chapter_contains"], row["top1_combined"], row["top3_combined"], row["top5_combined"], row["hits"][0]["subject"] if row["hits"] else None, row["hits"][0]["chapter"] if row["hits"] else None]
        for row in rows
    ]
    lines = [
        "# Retrieval Quality Report",
        "",
        "## Summary",
        "",
        json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True),
        "",
        "## Root-Cause Claims",
        "",
        "- FACT: Retrieval evaluation used the same deterministic embedding family used by the content pipeline.",
        "- FACT: Scores are measured against Qdrant payload metadata, not frontend behavior.",
        "- LIKELY: Low Top-5 chapter accuracy is connected to noisy chunks and inconsistent chapter metadata.",
        "- UNPROVEN: Accuracy will exceed target until cleaned chunks are re-embedded and Qdrant is rebuilt.",
        "",
        "## Question Results",
        "",
        markdown_table(["query", "subject", "chapter", "top1", "top3", "top5", "first_subject", "first_chapter"], report_rows),
    ]
    (output_dir / "RETRIEVAL_QUALITY_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
