from __future__ import annotations

from collections import defaultdict


class ConceptLinker:
    """Build lightweight concept-to-concept association graph."""

    def link(self, chunks: list[dict]) -> dict[str, list[str]]:
        adjacency: dict[str, set[str]] = defaultdict(set)

        for chunk in chunks:
            concepts = [str(c).strip().lower() for c in chunk.get("metadata", {}).get("concepts", []) if str(c).strip()]
            unique = list(dict.fromkeys(concepts))
            for left in unique:
                for right in unique:
                    if left != right:
                        adjacency[left].add(right)

        return {key: sorted(values) for key, values in adjacency.items()}
