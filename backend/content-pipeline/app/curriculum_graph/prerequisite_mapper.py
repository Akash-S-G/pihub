from __future__ import annotations


class PrerequisiteMapper:
    """Infer topic prerequisites with a conservative heuristic model."""

    ORDER_HINTS = ["introduction", "basics", "fundamentals", "overview"]

    def map_prerequisites(self, ordered_topics: list[str]) -> dict[str, list[str]]:
        cleaned = [topic.strip().lower() for topic in ordered_topics if topic and topic.strip()]
        prerequisites: dict[str, list[str]] = {}

        for i, topic in enumerate(cleaned):
            if i == 0:
                prerequisites[topic] = []
                continue

            prev_topic = cleaned[i - 1]
            current_prereqs: list[str] = [prev_topic]

            # Introductory topics are also prerequisites for later advanced topics.
            for j in range(i):
                candidate = cleaned[j]
                if any(hint in candidate for hint in self.ORDER_HINTS) and candidate not in current_prereqs:
                    current_prereqs.append(candidate)

            prerequisites[topic] = current_prereqs

        return prerequisites
