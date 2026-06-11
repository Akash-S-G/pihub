from __future__ import annotations

import unittest

from app.evaluation.quality_scoring import QualityScorer
from app.pack_system.checksum_generator import ChecksumGenerator
from app.sync.delta_builder import DeltaBuilder
from app.sync.pack_diff_engine import PackDiffEngine
from app.sync.sync_manifest_generator import SyncManifestGenerator
from app.validation.pack_validator import PackValidator


class PackValidationSyncTests(unittest.TestCase):
    def test_pack_validator_and_scoring(self) -> None:
        manifest = {
            "pack_id": "grade7_science_nutrition_in_plants",
            "version": "1.0.0",
            "grade": 7,
            "subject": "science",
            "chapter": "Nutrition in Plants",
            "language": "english",
            "generated_at": "2026-05-18T12:00:00Z",
            "checksum": "sha256:abc",
            "content_checksum": "sha256:def",
            "retrieval_index_version": "v2",
            "artifact_counts": {"content": 1, "glossary": 1, "quizzes": 1, "flashcards": 1, "summaries": 1, "enrichment": 1, "retrieval_index": 1},
            "generation_metadata": {},
        }
        manifest["checksum"] = ChecksumGenerator.checksum_dict({key: value for key, value in manifest.items() if key != "checksum"})
        artifacts = {
            "content": [{"chunk_id": "c1"}],
            "glossary": [{"term": "photosynthesis", "definition": "process"}],
            "quizzes": [{"question": "Q?", "correct_answer": "A"}],
            "flashcards": [{"front": "f", "back": "b"}],
            "summaries": [{"title": "Summary", "text": "..."}],
            "enrichment": {"related_topics": ["light"]},
            "retrieval_index": {"vectors": 1},
        }

        validation = PackValidator().validate(manifest, artifacts, {"retrieval_score": 0.9})
        self.assertTrue(validation.valid, validation.errors)
        scores = QualityScorer().score(manifest, artifacts)
        self.assertGreaterEqual(scores.overall_score, 0.0)
        self.assertLessEqual(scores.overall_score, 1.0)

    def test_sync_helpers(self) -> None:
        host_records = [
            {"pack_id": "grade7_science_nutrition_in_plants", "version": "1.0.1", "checksum": "sha256:1", "content_checksum": "sha256:c", "compressed_size_mb": 2.5, "grade": 7, "subject": "science", "chapter": "Nutrition in Plants", "language": "english"},
            {"pack_id": "grade7_math_fractions", "version": "1.0.0", "checksum": "sha256:2", "content_checksum": "sha256:d", "compressed_size_mb": 1.0, "grade": 7, "subject": "math", "chapter": "Fractions", "language": "english"},
        ]
        delta = DeltaBuilder().build(host_records, {"grade7_math_fractions": "1.0.0"})
        self.assertIn("grade7_science_nutrition_in_plants", delta["packs_to_add"])
        self.assertEqual(delta["packs_to_remove"], [])

        sync_manifest = SyncManifestGenerator().generate("1.0.0", host_records)
        self.assertEqual(sync_manifest["total_packs"], 2)
        self.assertIn("checksum", sync_manifest)

        diff = PackDiffEngine().diff({"version": "1.0.0", "checksum": "sha256:1", "content_checksum": "sha256:a", "artifact_counts": {"content": 1}}, {"version": "1.0.1", "checksum": "sha256:2", "content_checksum": "sha256:b", "artifact_counts": {"content": 2}})
        self.assertEqual(diff["version_comparison"], -1)
        self.assertTrue(diff["checksum_changed"])


if __name__ == "__main__":
    unittest.main()
