from __future__ import annotations

from typing import Any

from .common import GENERIC_TERMS, has_boilerplate, percent, token_set, word_count


class FlashcardEvaluator:
    def classify_card(self, front: str, back: str) -> str:
        text = f"{front} {back}".lower()
        if any(symbol in text for symbol in ["=", "×", "÷", "formula"]):
            return "Formula"
        if any(word in text for word in ["because", "therefore", "leads to", "causes"]):
            return "Cause-Effect"
        if word_count(back) <= 18:
            return "Definition"
        if any(word in text for word in ["process", "system", "relationship", "principle"]):
            return "Concept"
        return "Fact"

    def evaluate_pack(self, pack: dict[str, Any], artifacts: dict[str, Any]) -> list[dict[str, Any]]:
        source_terms = token_set(" ".join(str(item.get("text") or "") for item in artifacts.get("content", [])))
        rows = []
        for card in artifacts.get("flashcards", []):
            front = str(card.get("front") or "")
            back = str(card.get("back") or "")
            low_value = has_boilerplate(front) or has_boilerplate(back) or front.lower() in GENERIC_TERMS
            rows.append(
                {
                    "pack_id": pack.get("pack_id"),
                    "front": front,
                    "card_type": self.classify_card(front, back),
                    "concept_usefulness": word_count(front) >= 1 and word_count(back) >= 5 and not low_value,
                    "memorization_value": len(front) <= 90 and 20 <= len(back) <= 420,
                    "educational_relevance": bool(token_set(f"{front} {back}") & source_terms),
                    "low_value": low_value,
                }
            )
        for row in rows:
            row["passed"] = row["concept_usefulness"] and row["memorization_value"] and row["educational_relevance"] and not row["low_value"]
        return rows

    def evaluate(self, packs: list[dict[str, Any]], artifact_loader) -> dict[str, Any]:
        rows = []
        for pack in packs:
            rows.extend(self.evaluate_pack(pack, artifact_loader(pack))[:10])
        score = percent(sum(1 for row in rows if row["passed"]), len(rows))
        return {"flashcard_quality": score, "sampled_flashcards": len(rows), "failures": [row for row in rows if not row["passed"]], "rows": rows}
