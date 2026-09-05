from __future__ import annotations

import unittest

from app.educational_intelligence import (
    EnrichmentRouter,
    FlashcardGenerator,
    GlossaryExtractor,
    PackCompiler,
    QualityEvaluator,
    QuizGenerator,
    SummaryGenerator,
)


class EducationalIntelligenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.chunks = [
            {
                "text": "Photosynthesis is the process by which plants make food. Chlorophyll is the green pigment.",
                "metadata": {
                    "chapter": "Nutrition in Plants",
                    "subject": "science",
                    "grade": 7,
                    "topics": ["photosynthesis"],
                    "chunk_type": "definition",
                },
            },
            {
                "text": "Equation: 6CO2 + 6H2O = C6H12O6 + 6O2",
                "metadata": {
                    "chapter": "Nutrition in Plants",
                    "subject": "science",
                    "grade": 7,
                    "topics": ["photosynthesis"],
                    "chunk_type": "formula",
                },
            },
        ]

        self.noisy_chunks = [
            {
                "text": "Both Assertion And Reason. /square6 The following question is based on Assertion/Reason.",
                "metadata": {
                    "chapter": "Light Mirrors and Lenses",
                    "subject": "science",
                    "grade": 10,
                    "topics": ["Both Assertion And Reason", "Mirror", "Convex"],
                    "chunk_type": "definition",
                },
            },
            {
                "text": "The laws of reflection are valid for all kinds of mirrors.",
                "metadata": {
                    "chapter": "Light Mirrors and Lenses",
                    "subject": "science",
                    "grade": 10,
                    "topics": ["Laws of reflection", "Mirror"],
                    "chunk_type": "definition",
                },
            },
        ]

    def test_summary_generation(self) -> None:
        summary = SummaryGenerator().generate(self.chunks, chapter="Nutrition in Plants")
        self.assertEqual(summary["chapter"], "Nutrition in Plants")
        self.assertTrue(summary["summary"])

    def test_glossary_and_flashcards(self) -> None:
        glossary = GlossaryExtractor().extract(self.chunks)
        cards = FlashcardGenerator().generate(self.chunks)
        self.assertGreaterEqual(len(glossary), 1)
        self.assertGreaterEqual(len(cards), 1)
        self.assertTrue(all("What does the chapter say about" in card["front"] for card in cards))

    def test_quiz_generation(self) -> None:
        quizzes = QuizGenerator().generate(self.chunks, limit=4)
        self.assertGreaterEqual(len(quizzes), 3)
        self.assertTrue(all("question" in quiz for quiz in quizzes))
        mcqs = [quiz for quiz in quizzes if quiz.get("question_type") == "mcq"]
        self.assertTrue(mcqs)
        self.assertTrue(all(quiz["answer"] in [option for option in quiz["options"]] for quiz in mcqs))

    def test_noise_is_filtered_from_glossary(self) -> None:
        glossary = GlossaryExtractor().extract(self.noisy_chunks)
        terms = {entry["term"].lower() for entry in glossary}
        self.assertNotIn("both assertion and reason", terms)
        self.assertIn("laws of reflection", terms)
        self.assertTrue(all("/square6" not in entry["definition"].lower() for entry in glossary))

    def test_pack_compilation_and_evaluation(self) -> None:
        summary = SummaryGenerator().generate(self.chunks, chapter="Nutrition in Plants")
        glossary = GlossaryExtractor().extract(self.chunks)
        quizzes = QuizGenerator().generate(self.chunks, limit=4)
        flashcards = FlashcardGenerator().generate(self.chunks)
        enrichment = EnrichmentRouter().route("photosynthesis", grade=7, subject="science")
        pack = PackCompiler().compile(
            "Nutrition in Plants",
            self.chunks,
            [summary],
            glossary,
            quizzes,
            flashcards,
            enrichment["resources"],
        )
        evaluation = QualityEvaluator().evaluate(self.chunks, quizzes, glossary)
        self.assertTrue(pack["archive_path"].endswith(".zip"))
        self.assertGreaterEqual(evaluation["quality_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
