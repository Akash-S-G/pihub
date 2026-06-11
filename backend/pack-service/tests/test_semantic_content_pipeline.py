from __future__ import annotations

import unittest

from app.semantic_content_pipeline import SemanticContentPipeline


class SemanticContentPipelineTests(unittest.TestCase):
    def test_cleans_deduplicates_separates_and_gates_pack_content(self) -> None:
        concept = (
            "Photosynthesis is the process by which green plants use sunlight, carbon dioxide, and water "
            "to prepare food. Chlorophyll helps leaves capture light energy. This process releases oxygen "
            "and supports life on Earth. Students should understand that plants make food in leaves and do "
            "not simply absorb food from soil. "
        ) * 5
        chunks = [
            {
                "chunk_id": "toc",
                "text": "Contents\nChapter 1 .... 5\nChapter 2 .... 12\nChapter 3 .... 20",
                "metadata": {"grade": 8, "subject": "science", "chapter": "plant life"},
            },
            {
                "chunk_id": "concept_1",
                "text": concept,
                "metadata": {"grade": 8, "subject": "science", "chapter": "plant life", "topic": "photosynthesis"},
            },
            {
                "chunk_id": "concept_2",
                "text": concept,
                "metadata": {"grade": 8, "subject": "science", "chapter": "plant life", "topic": "photosynthesis"},
            },
            {
                "chunk_id": "exercise_1",
                "text": "Exercise: What is photosynthesis? Explain with examples.",
                "metadata": {"grade": 8, "subject": "science", "chapter": "plant life"},
            },
        ]

        result = SemanticContentPipeline().build(
            chunks,
            pack_id="sample_grade8_science",
            metadata={"grade": 8, "subject": "science", "chapter": "plant life", "language": "english"},
        )

        self.assertTrue(result.quality_gate["passed"], result.quality_gate)
        self.assertEqual(result.reports["content_cleanup"]["removed_chunks"], 1)
        self.assertEqual(result.reports["deduplication"]["duplicates_removed"], 1)
        self.assertEqual(len(result.artifacts["questions"]), 1)
        self.assertGreaterEqual(len(result.artifacts["concepts"]), 1)
        self.assertTrue(all(item["metadata"]["rag_eligible"] for item in result.artifacts["content"]))
        textbook = result.artifacts["textbook"]
        self.assertEqual(textbook["metadata"]["artifact_type"], "structured_textbook")
        self.assertGreaterEqual(len(textbook["sections"]), 1)
        block_types = {
            block["type"]
            for section in textbook["sections"]
            for block in section["blocks"]
        }
        self.assertIn("heading", block_types)
        self.assertTrue({"paragraph", "definition"} & block_types)
        self.assertTrue(result.reports["textbook_publication"]["publication_ready"])
        self.assertEqual(result.quality_gate["metrics"]["duplicate_ratio"], 0.0)
        self.assertGreaterEqual(result.quality_gate["metrics"]["average_chunk_length"], 200)
        self.assertLessEqual(result.quality_gate["metrics"]["average_chunk_length"], 400)


if __name__ == "__main__":
    unittest.main()
