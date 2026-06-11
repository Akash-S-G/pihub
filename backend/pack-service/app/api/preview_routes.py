from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from .pack_response_models import PackValidationReport


router = APIRouter(tags=["Internal Debug"])


def _repository(request: Request):
    return request.app.state.pack_repository


def _load_json(path: Path) -> Any:
    import json

    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/debug/packs/{pack_id}")
def debug_pack_manifest(pack_id: str, request: Request, version: str | None = Query(default=None)) -> dict[str, Any]:
    manifest = _repository(request).load_manifest(pack_id, version)
    record = _repository(request).get_pack(pack_id, version)
    if manifest is None or record is None:
        raise HTTPException(status_code=404, detail="Pack not found")

    pack_dir = Path(record["pack_dir"])
    return {
        "manifest": manifest,
        "chunks": _load_json(pack_dir / "content.json"),
        "glossary": _load_json(pack_dir / "glossary.json"),
        "quizzes": _load_json(pack_dir / "quizzes.json"),
        "flashcards": _load_json(pack_dir / "flashcards.json"),
        "summaries": _load_json(pack_dir / "summaries.json"),
        "enrichment": _load_json(pack_dir / "enrichment.json"),
        "retrieval_index": _load_json(pack_dir / "retrieval_index" / "index.json"),
    }


@router.get("/debug/packs/{pack_id}/validation")
def debug_validation(pack_id: str, request: Request, version: str | None = Query(default=None)) -> dict[str, Any]:
    manifest = _repository(request).load_manifest(pack_id, version)
    record = _repository(request).get_pack(pack_id, version)
    if manifest is None or record is None:
        raise HTTPException(status_code=404, detail="Pack not found")
    pack_dir = Path(record["pack_dir"])
    artifacts = {
        "content": _load_json(pack_dir / "content.json"),
        "glossary": _load_json(pack_dir / "glossary.json"),
        "quizzes": _load_json(pack_dir / "quizzes.json"),
        "flashcards": _load_json(pack_dir / "flashcards.json"),
        "summaries": _load_json(pack_dir / "summaries.json"),
        "enrichment": _load_json(pack_dir / "enrichment.json"),
        "retrieval_index": _load_json(pack_dir / "retrieval_index" / "index.json"),
    }
    result = request.app.state.pack_validator.validate(manifest, artifacts, request.app.state.quality_scorer.score(manifest, artifacts).model_dump())
    return PackValidationReport(pack_id=pack_id, version=str(manifest.get("version", "1.0.0")), valid=result.valid, errors=result.errors, warnings=result.warnings).model_dump()


@router.get("/debug/reports/{pack_id}")
def debug_reports(pack_id: str, request: Request, version: str | None = Query(default=None)) -> dict[str, Any]:
    manifest = _repository(request).load_manifest(pack_id, version)
    record = _repository(request).get_pack(pack_id, version)
    if manifest is None or record is None:
        raise HTTPException(status_code=404, detail="Pack not found")
    pack_dir = Path(record["pack_dir"])
    artifacts = {
        "content": _load_json(pack_dir / "content.json"),
        "glossary": _load_json(pack_dir / "glossary.json"),
        "quizzes": _load_json(pack_dir / "quizzes.json"),
        "flashcards": _load_json(pack_dir / "flashcards.json"),
        "summaries": _load_json(pack_dir / "summaries.json"),
        "enrichment": _load_json(pack_dir / "enrichment.json"),
        "retrieval_index": _load_json(pack_dir / "retrieval_index" / "index.json"),
    }
    quality_scores = request.app.state.quality_scorer.score(manifest, artifacts)
    benchmark = request.app.state.retrieval_benchmark.run(request.app.state.pack_repository.list_packs())
    return {
        "manifest": manifest,
        "quality_scores": quality_scores.model_dump(),
        "benchmark": benchmark.model_dump(),
    }
