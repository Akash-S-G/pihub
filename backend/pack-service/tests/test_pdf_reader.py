from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.pdf_reader import PdfRegistrationService, PdfRepository


PDF_BYTES = b"%PDF-1.4\n1 0 obj << /Type /Page >> endobj\n2 0 obj << /Type /Page >> endobj\n%%EOF"


class PdfReaderTests(unittest.TestCase):
    def test_scan_library_generates_manifest_and_resolves_chapter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pdf_dir = root / "TEXTBOOKS" / "mathematics" / "class 8"
            pdf_dir.mkdir(parents=True)
            pdf_path = pdf_dir / "Proportional Reasoning.pdf"
            pdf_path.write_bytes(PDF_BYTES)

            manifest_path = root / "pdf_manifest.json"
            repository = PdfRepository(manifest_path, library_root=root / "TEXTBOOKS")
            service = PdfRegistrationService(repository, root / "TEXTBOOKS")

            report = service.scan_library()
            self.assertEqual(report["pdfs_registered"], 1)
            self.assertEqual(report["books_discovered"], 1)
            self.assertEqual(report["chapters_mapped"], 1)
            self.assertTrue(manifest_path.exists())

            reference = repository.resolve_pdf_reference(8, "maths", "Proportional Reasoning", "english")
            self.assertIsNotNone(reference)
            assert reference is not None
            self.assertEqual(reference.start_page, 1)
            self.assertEqual(reference.end_page, 2)
            self.assertEqual(reference.subject, "maths")
            self.assertTrue(Path(reference.pdf_path).exists())
            self.assertEqual(repository.get_chapter_page_range(reference.chapter_id), (1, 2))
            self.assertEqual(len(repository.get_books(8, "maths", "english")), 1)
            catalog = service.catalog_payload()
            self.assertEqual(catalog["total_entries"], 1)
            self.assertEqual(catalog["entries"][0]["chapter"], "Proportional Reasoning")

    def test_rebuild_catalog_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pdf_path = root / "science" / "class 6" / "Chapter 1 Science.pdf"
            pdf_path.parent.mkdir(parents=True)
            pdf_path.write_bytes(PDF_BYTES)

            repository = PdfRepository(root / "pdf_manifest.json", library_root=root)
            service = PdfRegistrationService(repository, root)
            first = service.scan_library()
            second = service.scan_library()

            self.assertEqual(first["books_discovered"], 1)
            self.assertEqual(second["books_discovered"], 1)
            self.assertEqual(second["duplicate_registrations"], 0)
            self.assertEqual(len(repository.list_books()), 1)


if __name__ == "__main__":
    unittest.main()
