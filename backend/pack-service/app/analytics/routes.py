from __future__ import annotations

from fastapi import APIRouter, Query, Request

from .coverage_analyzer import PackCoverageAnalyzer
from shared.text_normalization import normalize_language_code


router = APIRouter(tags=["Pack Analytics"])


@router.get("/analytics/pack-coverage")
async def pack_coverage(request: Request) -> dict:
    repository = request.app.state.pack_repository
    analyzer = PackCoverageAnalyzer()
    return analyzer.analyze(repository.list_packs())


@router.get("/packs/coverage")
async def pack_coverage_alias(request: Request) -> dict:
    repository = request.app.state.pack_repository
    analyzer = PackCoverageAnalyzer()
    return analyzer.analyze(repository.list_packs())


@router.get("/packs/multilingual/plan")
async def multilingual_pack_plan(
    request: Request,
    target_language: str = Query(default="hi"),
    grade: int | None = Query(default=None),
    subject: str | None = Query(default=None),
) -> dict:
    target_language = normalize_language_code(target_language) or target_language
    packs = request.app.state.pack_repository.list_packs()
    planned = []
    for pack in packs:
        if grade is not None and pack.get("grade") != grade:
            continue
        if subject and str(pack.get("subject") or "").lower() != subject.lower():
            continue
        counts = pack.get("artifact_counts") or {}
        planned.append({
            "source_pack_id": pack.get("pack_id"),
            "target_language": target_language,
            "grade": pack.get("grade"),
            "subject": pack.get("subject"),
            "chapter": pack.get("chapter"),
            "translatable_artifacts": {
                "summaries": int(counts.get("summaries") or 0),
                "glossary": int(counts.get("glossary") or 0),
                "concepts": int(counts.get("concepts") or 0),
                "chapter_knowledge": int(counts.get("chapter_knowledge") or 0),
            },
        })
    return {
        "target_language": target_language,
        "count": len(planned),
        "packs": planned,
        "status": "plan_only",
    }
