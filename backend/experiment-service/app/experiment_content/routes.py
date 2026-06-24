from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.experiment_content.service import ExperimentContentService


router = APIRouter(tags=["Experiment Content"])
service = ExperimentContentService()


@router.get("/experiments/catalog")
async def experiment_catalog() -> dict[str, object]:
    import json
    from pathlib import Path
    
    experiments = service.catalog()
    catalog_path = Path("/shared/simulations/catalog.json")
    simulations = []
    
    if catalog_path.exists():
        with catalog_path.open() as f:
            simulations = json.load(f)
            
        for sim in simulations:
            slug = sim.get("slug")
            sim["local_url"] = f"/simulations/{slug}/index.html"
            sim["manifest"] = {
                "id": f"phet-{slug}",
                "title": slug.replace("-", " ").title(),
                "provider": "phet",
                "type": "simulation"
            }
            
    return {
        "experiments": experiments, 
        "simulations": simulations,
        "total": len(experiments) + len(simulations)
    }


@router.get("/experiments/{experiment_id}/download")
async def download_experiment_pack(experiment_id: str) -> StreamingResponse:
    data = service.package_bytes(experiment_id)
    return StreamingResponse(
        iter([data]),
        media_type="application/gzip",
        headers={
            "Content-Disposition": f'attachment; filename="{experiment_id}.experiment-pack.tar.gz"',
            "Content-Length": str(len(data)),
        },
    )


@router.get("/experiments/{experiment_id}/certification")
async def experiment_certification(experiment_id: str) -> dict[str, object]:
    return service.certification(experiment_id).model_dump(mode="json")


@router.get("/chapters/{chapter_id}/experiments")
async def chapter_experiments(chapter_id: str) -> dict[str, object]:
    return service.chapter_experiments(chapter_id)
