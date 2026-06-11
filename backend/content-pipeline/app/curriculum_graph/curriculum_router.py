from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RoutingResult:
    filters: dict[str, Any]
    expanded_topics: list[str]
    prerequisite_topics: list[str]
    related_topics: list[str]


class CurriculumRouter:
    """Curriculum-aware routing for retrieval filter augmentation."""

    def __init__(self, curriculum_graph: Any, relation_graph: dict[str, Any]) -> None:
        self.curriculum_graph = curriculum_graph
        self.relation_graph = relation_graph

    def route(self, query: str, incoming_filters: dict[str, Any] | None = None) -> RoutingResult:
        filters = dict(incoming_filters or {})

        inferred_subject = self.curriculum_graph.infer_subject_for_query(query)
        inferred_topics = [t.lower() for t in self.curriculum_graph.infer_topics_for_query(query)]

        if inferred_subject and "subject" not in filters:
            filters["subject"] = inferred_subject
        if inferred_topics and "topic" not in filters:
            filters["topic"] = inferred_topics[0]

        topic_relations = self.relation_graph.get("topic_relations", {})
        prerequisites = self.relation_graph.get("prerequisites", {})

        related_topics: list[str] = []
        prerequisite_topics: list[str] = []
        expanded = list(inferred_topics)

        for topic in inferred_topics:
            related = topic_relations.get(topic, [])
            prereq = prerequisites.get(topic, [])
            for item in related:
                if item not in related_topics:
                    related_topics.append(item)
                if item not in expanded:
                    expanded.append(item)
            for item in prereq:
                if item not in prerequisite_topics:
                    prerequisite_topics.append(item)
                if item not in expanded:
                    expanded.append(item)

        return RoutingResult(
            filters=filters,
            expanded_topics=expanded,
            prerequisite_topics=prerequisite_topics,
            related_topics=related_topics,
        )
