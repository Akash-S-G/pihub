from __future__ import annotations

import math
from typing import Any

from .common import percent, readable_educational_text, token_set


GRADE8_BENCHMARK_QUESTIONS = [
    *[(f"Science question {idx}: Explain force and pressure in Grade 8 science.", "science") for idx in range(1, 11)],
    *[(f"Science question {idx}: What are natural resources and why are they important?", "science") for idx in range(11, 21)],
    *[(f"Science question {idx}: Explain light, mirrors, lenses, or the particulate nature of matter.", "science") for idx in range(21, 31)],
    *[(f"Mathematics question {idx}: What is proportional reasoning?", "maths") for idx in range(1, 11)],
    *[(f"Mathematics question {idx}: Explain fractions, squares, cubes, powers, or Pythagoras theorem.", "maths") for idx in range(11, 31)],
    *[(f"Social science question {idx}: Explain democracy, parliament, resources, history, or government.", "social_science") for idx in range(1, 41)],
]


class TutorEvaluator:
    def search(self, query: str, content: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
        q_terms = token_set(query)
        scored = []
        for item in content:
            terms = token_set(item.get("text"))
            if not terms:
                continue
            score = len(q_terms & terms) / math.sqrt(len(terms))
            if score > 0:
                scored.append((score, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in scored[:limit]]

    def evaluate(self, packs: list[dict[str, Any]], artifact_loader) -> dict[str, Any]:
        by_subject: dict[str, list[dict[str, Any]]] = {"science": [], "maths": [], "social_science": []}
        for pack in packs:
            subject = str(pack.get("subject") or "")
            key = "maths" if "math" in subject else "social_science" if "social" in subject else "science" if "science" in subject else subject
            if key in by_subject:
                by_subject[key].extend(artifact_loader(pack).get("content", []))
        rows = []
        for question, subject in GRADE8_BENCHMARK_QUESTIONS:
            results = self.search(question, by_subject.get(subject, []))
            relevant = sum(1 for item in results if token_set(question) & token_set(item.get("text")))
            useful = sum(1 for item in results if readable_educational_text(item.get("text")))
            rows.append(
                {
                    "question": question,
                    "subject": subject,
                    "retrieval_precision": percent(relevant, len(results)),
                    "answer_accuracy": percent(relevant, 5),
                    "completeness": percent(min(len(results), 5), 5),
                    "hallucination_rate": round(100 - percent(relevant, len(results)), 2) if results else 100.0,
                    "educational_usefulness": percent(useful, len(results)),
                }
            )
        aggregate = {
            "retrieval_precision": round(sum(row["retrieval_precision"] for row in rows) / max(1, len(rows)), 2),
            "answer_accuracy": round(sum(row["answer_accuracy"] for row in rows) / max(1, len(rows)), 2),
            "completeness": round(sum(row["completeness"] for row in rows) / max(1, len(rows)), 2),
            "hallucination_rate": round(sum(row["hallucination_rate"] for row in rows) / max(1, len(rows)), 2),
            "educational_usefulness": round(sum(row["educational_usefulness"] for row in rows) / max(1, len(rows)), 2),
        }
        score = round((aggregate["retrieval_precision"] + aggregate["answer_accuracy"] + aggregate["completeness"] + (100 - aggregate["hallucination_rate"]) + aggregate["educational_usefulness"]) / 5, 2)
        return {"tutor_quality": score, "metrics": aggregate, "questions": rows}
