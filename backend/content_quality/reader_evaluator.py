from __future__ import annotations

from collections import Counter
from typing import Any

from .common import key_terms, percent, readable_educational_text, token_set, word_count


class ReaderEvaluator:
    def evaluate_pack(self, pack: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]:
        content = artifacts.get("content", [])
        concepts = artifacts.get("concepts", [])
        examples = artifacts.get("examples", [])
        worked = artifacts.get("worked_examples", [])
        rows = []
        pass_count = 0
        for item in content:
            text = str(item.get("text") or "")
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            ok = readable_educational_text(text)
            pass_count += int(ok)
            rows.append(
                {
                    "chunk_id": item.get("chunk_id"),
                    "content_type": metadata.get("content_type"),
                    "words": word_count(text),
                    "passed": ok,
                }
            )
        concept_terms = token_set(" ".join(str(item.get("text") or "") for item in concepts))
        all_terms = token_set(" ".join(str(item.get("text") or "") for item in content))
        concept_retention = percent(len(concept_terms & all_terms), max(1, len(concept_terms)))
        score = percent(pass_count, len(content))
        flow_score = min(100.0, score + min(15.0, len(concepts) * 1.5) + min(10.0, (len(examples) + len(worked)) * 2.0))
        return {
            "pack_id": pack.get("pack_id"),
            "chapter": pack.get("chapter"),
            "subject": pack.get("subject"),
            "reader_score": round((score * 0.65) + (concept_retention * 0.2) + (flow_score * 0.15), 2),
            "concept_retention": concept_retention,
            "example_retention": len(examples),
            "worked_example_retention": len(worked),
            "definition_retention": len([term for term in key_terms(" ".join(str(item.get("text") or "") for item in content)) if term]),
            "narrative_flow": round(flow_score, 2),
            "missing_concepts": [],
            "missing_examples": max(0, 3 - len(examples)),
            "rows": rows[:50],
        }

    def evaluate(self, packs: list[dict[str, Any]], artifact_loader) -> dict[str, Any]:
        rows = [self.evaluate_pack(pack, artifact_loader(pack)) for pack in packs]
        score = round(sum(row["reader_score"] for row in rows) / max(1, len(rows)), 2)
        failures = [row for row in rows if row["reader_score"] < 90]
        subject_scores = Counter()
        subject_counts = Counter()
        for row in rows:
            subject_scores[str(row.get("subject"))] += row["reader_score"]
            subject_counts[str(row.get("subject"))] += 1
        return {
            "reader_quality": score,
            "subject_scores": {subject: round(subject_scores[subject] / subject_counts[subject], 2) for subject in subject_scores},
            "failures": failures,
            "rows": rows,
        }
