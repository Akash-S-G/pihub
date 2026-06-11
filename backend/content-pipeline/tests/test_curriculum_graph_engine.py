from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.append(str(Path(__file__).resolve().parents[1]))
sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.curriculum_graph.concept_index import ConceptIndex
from app.curriculum_graph.curriculum_router import CurriculumRouter
from app.curriculum_graph.graph_builder import GraphBuilder

from shared.curriculum_graph import Chapter, Concept, CurriculumGraph, Grade, Subject, Topic


class CurriculumGraphEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = CurriculumGraph()
        self.builder = GraphBuilder()

    def _sample_graph(self) -> CurriculumGraph:
        graph = CurriculumGraph()

        graph.add_grade(Grade(level=10, name="Class 10", subjects=[]))

        grade = graph.get_grade(10)
        assert grade is not None

        grade.subjects = [
            Subject(
                name="maths",
                chapters=[
                    Chapter(
                        name="arithmetic progressions",
                        number=1,
                        topics=[
                            Topic(
                                name="arithmetic progression",
                                concepts=[
                                    Concept(name="common difference", description="The fixed number added to each term."),
                                    Concept(name="nth term", description="The general term of the sequence."),
                                ],
                            )
                        ],
                    ),
                    Chapter(
                        name="data handling and presentation",
                        number=2,
                        topics=[
                            Topic(
                                name="statistics",
                                concepts=[
                                    Concept(name="mean", description="Average value of a dataset."),
                                    Concept(name="median", description="Middle value when data are ordered."),
                                    Concept(name="mode", description="Most frequent value in a dataset."),
                                ],
                            )
                        ],
                    ),
                    Chapter(
                        name="triangles",
                        number=3,
                        topics=[
                            Topic(
                                name="triangles",
                                concepts=[
                                    Concept(name="similar triangles", description="Triangles with equal corresponding angles."),
                                ],
                            )
                        ],
                    ),
                    Chapter(
                        name="surface areas and volumes",
                        number=4,
                        topics=[
                            Topic(
                                name="surface area",
                                concepts=[
                                    Concept(name="cylinder", description="A solid with two circular faces and one curved surface."),
                                ],
                            )
                        ],
                    ),
                ],
            )
        ]

        return graph

    def _concept_index(self) -> ConceptIndex:
        graph = self._sample_graph()
        index = ConceptIndex()
        index.build_from_curriculum(
            graph,
            glossary_entries=[
                {
                    "term": "common difference",
                    "definition": "The fixed number added to each term in an arithmetic progression.",
                    "chapter": "arithmetic progressions",
                    "subject": "maths",
                    "source": "definition",
                },
                {
                    "term": "nth term",
                    "definition": "The general term of an arithmetic progression.",
                    "chapter": "arithmetic progressions",
                    "subject": "maths",
                    "source": "definition",
                },
                {
                    "term": "mean",
                    "definition": "Average value of a dataset.",
                    "chapter": "data handling and presentation",
                    "subject": "maths",
                    "source": "definition",
                },
                {
                    "term": "median",
                    "definition": "Middle value when data are ordered.",
                    "chapter": "data handling and presentation",
                    "subject": "maths",
                    "source": "definition",
                },
                {
                    "term": "mode",
                    "definition": "Most frequent value in a dataset.",
                    "chapter": "data handling and presentation",
                    "subject": "maths",
                    "source": "definition",
                },
                {
                    "term": "similar triangles",
                    "definition": "Triangles with equal corresponding angles.",
                    "chapter": "triangles",
                    "subject": "maths",
                    "source": "definition",
                },
                {
                    "term": "cylinder",
                    "definition": "A solid with two circular faces and one curved surface.",
                    "chapter": "surface areas and volumes",
                    "subject": "maths",
                    "source": "definition",
                },
            ],
        )
        return index

    def _sample_chunks(self) -> list[dict]:
        return [
            {
                "text": "Photosynthesis uses chlorophyll in leaves.",
                "metadata": {
                    "grade": 7,
                    "subject": "science",
                    "chapter": "Nutrition in Plants",
                    "topics": ["photosynthesis", "chlorophyll"],
                    "concepts": ["photosynthesis", "chlorophyll", "leaf structure"],
                },
            },
            {
                "text": "Plant cells contain chloroplasts where photosynthesis occurs.",
                "metadata": {
                    "grade": 7,
                    "subject": "science",
                    "chapter": "Nutrition in Plants",
                    "topics": ["plant cells", "photosynthesis"],
                    "concepts": ["plant cells", "chloroplast", "photosynthesis"],
                },
            },
        ]

    def test_graph_builder_creates_relation_sections(self) -> None:
        built = self.builder.build(self._sample_chunks())
        self.assertIn("topic_relations", built)
        self.assertIn("concept_links", built)
        self.assertIn("prerequisites", built)

    def test_router_expands_topics(self) -> None:
        built = self.builder.build(self._sample_chunks())
        router = CurriculumRouter(self.graph, built)
        route = router.route("Explain photosynthesis in leaves", {})
        self.assertIn("photosynthesis", route.expanded_topics)
        self.assertTrue(route.related_topics or route.prerequisite_topics or route.expanded_topics)

    def test_concept_index_routes_common_difference(self) -> None:
        index = self._concept_index()
        candidates, confidence, _ = index.route_query_to_chapters("What is the common difference?", self._sample_graph())
        self.assertGreaterEqual(confidence, 0.6)
        self.assertEqual(candidates[0], "arithmetic progressions")

    def test_concept_index_routes_statistics_concepts(self) -> None:
        index = self._concept_index()
        graph = self._sample_graph()
        for query in ["What is the mean of a dataset?", "What is the median?", "What is the mode?"]:
            candidates, confidence, _ = index.route_query_to_chapters(query, graph)
            self.assertGreaterEqual(confidence, 0.6)
            self.assertEqual(candidates[0], "data handling and presentation")

    def test_concept_index_routes_data_handling_terms(self) -> None:
        index = self._concept_index()
        graph = self._sample_graph()
        for query in ["What is the average?", "What is the dataset?", "What is data handling?"]:
            candidates, confidence, _ = index.route_query_to_chapters(query, graph)
            self.assertGreaterEqual(confidence, 0.6)
            self.assertEqual(candidates[0], "data handling and presentation")

    def test_concept_index_routes_geometry_concepts(self) -> None:
        index = self._concept_index()
        graph = self._sample_graph()

        candidates, confidence, _ = index.route_query_to_chapters("What are similar triangles?", graph)
        self.assertGreaterEqual(confidence, 0.6)
        self.assertEqual(candidates[0], "triangles")

        candidates, confidence, _ = index.route_query_to_chapters("What is the surface area of a cylinder?", graph)
        self.assertGreaterEqual(confidence, 0.6)
        self.assertEqual(candidates[0], "surface areas and volumes")


if __name__ == "__main__":
    unittest.main()
