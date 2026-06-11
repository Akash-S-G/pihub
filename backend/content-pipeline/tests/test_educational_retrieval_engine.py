from __future__ import annotations

import unittest

from app.retrieval_engine.educational_retrieval_engine import EducationalRetrievalEngine


class _Hit:
    def __init__(self, hit_id: str, score: float, payload: dict):
        self.id = hit_id
        self.score = score
        self.payload = payload


class EducationalRetrievalEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = EducationalRetrievalEngine()

    def test_exact_topic_prioritized_over_related(self) -> None:
        hits = [
            _Hit(
                "exact",
                0.55,
                {
                    "text": "Photosynthesis uses chlorophyll.",
                    "subject": "science",
                    "chapter": "Nutrition in Plants",
                    "topics": ["photosynthesis"],
                    "chunk_type": "definition",
                },
            ),
            _Hit(
                "related",
                0.60,
                {
                    "text": "Leaf structure supports plant health.",
                    "subject": "science",
                    "chapter": "Nutrition in Plants",
                    "topics": ["leaf structure"],
                    "chunk_type": "explanation",
                },
            ),
        ]

        ranked = self.engine.rank(
            query="What is photosynthesis?",
            hits=hits,
            limit=2,
            routed_filters={"subject": "science"},
            inferred_subject="science",
            inferred_topics=["photosynthesis"],
            prerequisite_topics=[],
            related_topics=["leaf structure"],
        )
        self.assertEqual(ranked[0]["id"], "exact")

    def test_chapter_match_boost(self) -> None:
        hits = [
            _Hit(
                "chapter_match",
                0.50,
                {
                    "text": "Chlorophyll is green pigment.",
                    "subject": "science",
                    "chapter": "Nutrition in Plants",
                    "topics": ["chlorophyll"],
                    "chunk_type": "definition",
                },
            ),
            _Hit(
                "cross_chapter",
                0.50,
                {
                    "text": "Respiration releases energy.",
                    "subject": "science",
                    "chapter": "Respiration in Organisms",
                    "topics": ["respiration"],
                    "chunk_type": "definition",
                },
            ),
        ]
        ranked = self.engine.rank(
            query="Explain chlorophyll in nutrition in plants",
            hits=hits,
            limit=2,
            routed_filters={"subject": "science", "chapter": "Nutrition in Plants"},
            inferred_subject="science",
            inferred_topics=["chlorophyll"],
            prerequisite_topics=[],
            related_topics=[],
        )
        self.assertEqual(ranked[0]["id"], "chapter_match")


if __name__ == "__main__":
    unittest.main()
