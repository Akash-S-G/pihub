from __future__ import annotations

import unittest

from app.content_pipeline.educational_chunker import EducationalChunkerV2


class EducationalChunkingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.chunker = EducationalChunkerV2()
        self.base = {
            "chapter": "Nutrition in Plants",
            "topic": "Photosynthesis",
            "language": "english",
            "grade": 7,
            "subject": "science",
        }

    def test_preserves_formula_as_atomic_chunk(self) -> None:
        text = (
            "Chapter 1: Nutrition in Plants\n\n"
            "Plants prepare food using photosynthesis.\n\n"
            "Formula: 6CO2 + 6H2O -> C6H12O6 + 6O2\n\n"
            "This equation shows glucose production."
        )
        chunks = self.chunker.chunk_educational(text, self.base)
        formula_chunks = [c for c in chunks if c["metadata"].get("chunk_type") == "formula"]
        self.assertTrue(formula_chunks)
        self.assertIn("6CO2", formula_chunks[0]["text"])

    def test_preserves_definition_block(self) -> None:
        text = (
            "Definition: Photosynthesis is the process by which plants make food using sunlight.\n\n"
            "Chlorophyll captures light energy."
        )
        chunks = self.chunker.chunk_educational(text, self.base)
        self.assertGreaterEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["metadata"].get("chunk_type"), "definition")

    def test_chunk_metadata_fields_present(self) -> None:
        text = "Example: Green leaves indicate chlorophyll activity under sunlight."
        chunks = self.chunker.chunk_educational(text, self.base)
        self.assertEqual(len(chunks), 1)
        metadata = chunks[0]["metadata"]
        for key in ["chapter", "topic", "chunk_type", "keywords", "language", "difficulty", "subject", "grade"]:
            self.assertIn(key, metadata)


if __name__ == "__main__":
    unittest.main()
