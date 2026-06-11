from __future__ import annotations

from collections import defaultdict


class TopicRelationBuilder:
    """Build related-topic graph from chapter-local co-occurrence."""

    def build(self, chunks: list[dict]) -> dict[str, list[str]]:
        by_chapter: dict[str, set[str]] = defaultdict(set)

        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            chapter = str(metadata.get("chapter") or "").strip().lower()
            topics = [str(topic).strip().lower() for topic in metadata.get("topics", []) if str(topic).strip()]
            if not chapter:
                continue
            by_chapter[chapter].update(topics)

        topic_relations: dict[str, set[str]] = defaultdict(set)
        for topics in by_chapter.values():
            topic_list = sorted(topics)
            for left in topic_list:
                for right in topic_list:
                    if left != right:
                        topic_relations[left].add(right)

        return {topic: sorted(related) for topic, related in topic_relations.items()}
