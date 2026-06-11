from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any


class PackCompiler:
    """Compile generated educational artifacts into an offline pack manifest/archive."""

    def compile(
        self,
        pack_name: str,
        chunks: list[dict[str, Any]],
        summaries: list[dict[str, Any]],
        glossary: list[dict[str, Any]],
        quizzes: list[dict[str, Any]],
        flashcards: list[dict[str, Any]],
        enrichment: list[dict[str, Any]],
        output_dir: Path | None = None,
    ) -> dict[str, Any]:
        output_root = output_dir or Path(tempfile.gettempdir()) / "pihub_packs"
        output_root.mkdir(parents=True, exist_ok=True)
        pack_dir = output_root / self._slug(pack_name)
        pack_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "pack_id": self._slug(pack_name),
            "pack_name": pack_name,
            "version": "1.0.0",
            "chunk_count": len(chunks),
            "summary_count": len(summaries),
            "glossary_count": len(glossary),
            "quiz_count": len(quizzes),
            "flashcard_count": len(flashcards),
            "enrichment_count": len(enrichment),
        }

        artifacts = {
            "content.json": chunks,
            "summaries.json": summaries,
            "glossary.json": glossary,
            "quizzes.json": quizzes,
            "flashcards.json": flashcards,
            "enrichment.json": enrichment,
            "metadata.json": manifest,
        }
        for filename, payload in artifacts.items():
            (pack_dir / filename).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

        archive_path = pack_dir.with_suffix(".zip")
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in pack_dir.iterdir():
                archive.write(file_path, arcname=file_path.name)

        manifest["archive_path"] = str(archive_path)
        manifest["pack_dir"] = str(pack_dir)
        return manifest

    def _slug(self, text: str) -> str:
        return "_".join(part for part in text.lower().split() if part)
