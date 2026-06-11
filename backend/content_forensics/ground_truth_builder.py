from __future__ import annotations

from collections import Counter
from typing import Any

from .common import extract_formulas, pack_records_for_pilot, qdrant_query_chunks, representative_terms


def build_ground_truth() -> list[dict[str, Any]]:
    rows = []
    for pilot, _record in pack_records_for_pilot():
        retrieved = qdrant_query_chunks(8, pilot.subject, pilot.chapter)
        texts = [str(chunk.get("text") or "") for chunk in retrieved]
        joined = "\n".join(texts)
        terms = representative_terms(joined, limit=40)
        definitions = []
        examples = []
        worked_examples = []
        objectives = []
        for chunk in retrieved:
            text = str(chunk.get("text") or "")
            lower = text.lower()
            if any(marker in lower for marker in (" is ", " are ", " is called ", " means ")):
                definitions.append(text[:600])
            if "example" in lower or "for example" in lower:
                examples.append(text[:800])
            if any(marker in lower for marker in ("solution", "solved", "therefore", "hence")):
                worked_examples.append(text[:1000])
            if any(marker in lower for marker in ("understand", "learn", "explain", "identify", "calculate", "observe")):
                objectives.append(text[:500])
        rows.append(
            {
                "pack_id": pilot.pack_id,
                "subject": pilot.subject,
                "chapter": pilot.chapter,
                "concepts": terms[:25],
                "definitions": definitions[:20],
                "formulae": extract_formulas(joined)[:20],
                "worked_examples": worked_examples[:20],
                "examples": examples[:20],
                "learning_objectives": objectives[:20] or [f"Understand key ideas in {pilot.chapter}."],
                "source_chunk_count": len(retrieved),
            }
        )
    return rows


def main() -> None:
    import json
    from pathlib import Path

    Path("ground_truth_concepts.json").write_text(json.dumps(build_ground_truth(), indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
