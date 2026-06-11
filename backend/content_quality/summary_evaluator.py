from __future__ import annotations

from typing import Any

from .common import percent, readable_educational_text, token_set, word_count


class SummaryEvaluator:
    def evaluate_pack(self, pack: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]:
        content_text = " ".join(str(item.get("text") or "") for item in artifacts.get("content", []))
        source_terms = token_set(content_text)
        rows = []
        pass_count = 0
        for summary in artifacts.get("summaries", []):
            text = str(summary.get("text") or summary.get("summary") or "")
            terms = token_set(text)
            coverage = percent(len(terms & source_terms), min(len(source_terms), 80))
            factual = bool(terms & source_terms) if source_terms else bool(terms)
            useful = readable_educational_text(text) or word_count(text) >= 45
            ok = factual and useful and coverage >= 35
            pass_count += int(ok)
            rows.append(
                {
                    "pack_id": pack.get("pack_id"),
                    "chapter": pack.get("chapter"),
                    "concept_coverage": coverage,
                    "factual_accuracy": factual,
                    "revision_usefulness": useful,
                    "passed": ok,
                    "missing_concepts": sorted(source_terms - terms)[:20],
                    "text": text[:900],
                }
            )
        score = percent(pass_count, len(rows))
        return {"pack_id": pack.get("pack_id"), "chapter": pack.get("chapter"), "summary_score": score, "rows": rows}

    def evaluate(self, packs: list[dict[str, Any]], artifact_loader) -> dict[str, Any]:
        rows = [self.evaluate_pack(pack, artifact_loader(pack)) for pack in packs]
        all_rows = [item for row in rows for item in row["rows"]]
        score = percent(sum(1 for row in all_rows if row["passed"]), len(all_rows))
        return {"summary_quality": score, "failures": [row for row in all_rows if not row["passed"]], "rows": rows}
