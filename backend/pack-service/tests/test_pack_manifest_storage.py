from __future__ import annotations

import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from app.pack_storage.pack_repository import PackRepository
from app.pack_system.checksum_generator import ChecksumGenerator
from app.pack_system.manifest_builder import ManifestBuilder
from app.pack_system.manifest_validator import ManifestValidator
from app.pack_system.version_manager import VersionManager
from app.pack_storage.storage_layout import StorageLayout


class PackManifestStorageTests(unittest.TestCase):
    def test_version_manager(self) -> None:
        self.assertEqual(VersionManager.compare("1.0.0", "1.0.1"), -1)
        self.assertEqual(VersionManager.bump_patch("1.0.0"), "1.0.1")
        self.assertEqual(VersionManager.bump_minor("1.0.0"), "1.1.0")
        self.assertEqual(VersionManager.bump_major("1.0.0"), "2.0.0")

    def test_manifest_builder_and_validator(self) -> None:
        builder = ManifestBuilder()
        manifest = builder.build(
            pack_id="grade7_science_nutrition_in_plants",
            grade=7,
            subject="science",
            chapter="Nutrition in Plants",
            language="english",
            version="1.0.0",
            artifact_counts={"content": 42, "quizzes": 15, "flashcards": 28, "summaries": 5, "glossary": 12, "enrichment": 3, "retrieval_index": 1},
            generation_metadata={"source": "unit-test"},
        )

        self.assertEqual(manifest["checksum"], ChecksumGenerator.checksum_dict({key: value for key, value in manifest.items() if key != "checksum"}))
        valid, errors = ManifestValidator().validate(manifest)
        self.assertTrue(valid, errors)

    def test_normalized_storage_and_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = PackRepository(Path(temp_dir))
            record = repository.save_pack(
                {
                    "pack_id": "grade7_science_nutrition_in_plants",
                    "grade": 7,
                    "subject": "science",
                    "chapter": "Nutrition in Plants",
                    "language": "english",
                    "version": "1.0.0",
                    "artifacts": {
                        "textbook": {
                            "pack_id": "grade7_science_nutrition_in_plants",
                            "title": "Grade 7 Science - Nutrition in Plants",
                            "metadata": {"artifact_type": "structured_textbook"},
                            "sections": [
                                {
                                    "section_id": "section_1",
                                    "title": "Nutrition In Plants",
                                    "blocks": [{"block_id": "b1", "type": "paragraph", "text": "Plants prepare food."}],
                                }
                            ],
                        },
                        "content": [{"chunk_id": "c1", "text": "photosynthesis"}],
                        "glossary": [{"term": "photosynthesis", "definition": "process"}],
                        "quizzes": [{"question": "Q?", "answer": "A"}],
                        "flashcards": [{"front": "f", "back": "b"}],
                        "summaries": [{"title": "Summary", "text": "..."}],
                        "enrichment": {"related_topics": ["light"]},
                        "retrieval_index": {"vectors": 1},
                    },
                    "generation_metadata": {"source": "unit-test"},
                }
            )

            pack_dir = Path(record["pack_dir"])
            self.assertEqual(pack_dir.relative_to(Path(temp_dir)).as_posix(), StorageLayout.pack_directory_name(7, "science", "Nutrition in Plants", "grade7_science_nutrition_in_plants"))
            self.assertTrue((pack_dir / "manifest.json").exists())
            self.assertTrue((pack_dir / "content.json").exists())
            self.assertTrue((pack_dir / "textbook.json").exists())
            self.assertTrue(Path(record["archive_path"]).exists())

            manifest = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["pack_id"], "grade7_science_nutrition_in_plants")
            self.assertEqual(manifest["artifact_counts"]["content"], 1)
            self.assertEqual(manifest["artifact_counts"]["textbook"], 1)
            textbook = json.loads((pack_dir / "textbook.json").read_text(encoding="utf-8"))
            self.assertEqual(textbook["metadata"]["artifact_type"], "structured_textbook")
            with tarfile.open(record["archive_path"], "r:gz") as archive:
                archive_files = {member.name.split("/", 1)[-1] for member in archive.getmembers() if member.isfile()}
            self.assertIn("textbook.json", archive_files)
            self.assertTrue(record["valid"])
            self.assertEqual(len(repository.list_packs()), 1)
            self.assertIsNotNone(repository.get_pack("grade7_science_nutrition_in_plants"))


if __name__ == "__main__":
    unittest.main()
