from __future__ import annotations

from app.curriculum_graph.concept_linker import ConceptLinker
from app.curriculum_graph.prerequisite_mapper import PrerequisiteMapper
from app.curriculum_graph.topic_relation_builder import TopicRelationBuilder


class GraphBuilder:
    """Aggregate topic relations, concept links, and prerequisites."""

    def __init__(self) -> None:
        self.topic_relation_builder = TopicRelationBuilder()
        self.concept_linker = ConceptLinker()
        self.prerequisite_mapper = PrerequisiteMapper()

    def build(self, chunks: list[dict], existing: dict | None = None) -> dict:
        base = dict(existing or {})
        topic_relations = self.topic_relation_builder.build(chunks)
        concept_links = self.concept_linker.link(chunks)

        # Infer prerequisites from all discovered topics in deterministic order.
        all_topics = sorted(topic_relations.keys())
        prerequisites = self.prerequisite_mapper.map_prerequisites(all_topics)

        base["topic_relations"] = topic_relations
        base["concept_links"] = concept_links
        base["prerequisites"] = prerequisites
        return base
