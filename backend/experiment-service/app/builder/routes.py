from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder

from app.core.pagination import page_query, page_size_query, paginate
from app.models.manifest_storage import CreateBuilderManifestRequest, UpdateBuilderManifestRequest
from app.services.manifest_storage_service import (
    BuilderManifestNotFoundError,
    BuilderManifestStateError,
    BuilderManifestValidationError,
    ManifestStorageService,
)


router = APIRouter(tags=["Experiment Builder"])
builder_service = ManifestStorageService()


def _dump(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    if hasattr(model, "dict"):
        return jsonable_encoder(model.dict())
    return jsonable_encoder(dict(model))


def _parse_model(model_type: Any, payload: dict[str, Any]) -> Any:
    if hasattr(model_type, "model_validate"):
        return model_type.model_validate(payload)
    return model_type.parse_obj(payload)


@router.post("/builder/manifests")
async def create_builder_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        request = _parse_model(CreateBuilderManifestRequest, payload)
        return _dump(builder_service.create_draft(request))
    except BuilderManifestValidationError as exc:
        raise HTTPException(status_code=400, detail={"errors": exc.errors}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/builder/manifests")
async def list_builder_manifests(
    owner_id: str | None = Query(default=None),
    page: int = page_query(),
    page_size: int = page_size_query(),
) -> dict[str, Any]:
    manifests = builder_service.list_manifests(owner_id)
    paged = paginate(manifests, page, page_size)
    return {
        "manifests": [_dump(manifest) for manifest in paged["items"]],
        "page": page,
        "page_size": page_size,
        "total": paged["total"],
    }


@router.put("/builder/manifests/{manifest_id}")
async def update_builder_manifest(manifest_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        request = _parse_model(UpdateBuilderManifestRequest, payload)
        return _dump(builder_service.update_draft(manifest_id, request))
    except BuilderManifestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BuilderManifestValidationError as exc:
        raise HTTPException(status_code=400, detail={"errors": exc.errors}) from exc
    except BuilderManifestStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/builder/manifests/{manifest_id}/publish")
async def publish_builder_manifest(manifest_id: str) -> dict[str, Any]:
    try:
        return _dump(builder_service.publish(manifest_id))
    except BuilderManifestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/builder/manifests/{manifest_id}/archive")
async def archive_builder_manifest(manifest_id: str) -> dict[str, Any]:
    try:
        return _dump(builder_service.archive(manifest_id))
    except BuilderManifestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/builder/manifests/{manifest_id}/revisions")
async def builder_manifest_revisions(
    manifest_id: str,
    page: int = page_query(),
    page_size: int = page_size_query(),
) -> dict[str, Any]:
    try:
        revisions = builder_service.revision_history(manifest_id)
    except BuilderManifestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    paged = paginate(revisions, page, page_size)
    return {
        "manifest_id": manifest_id,
        "revisions": [_dump(revision) for revision in paged["items"]],
        "page": page,
        "page_size": page_size,
        "total": paged["total"],
    }


@router.get("/builder/manifests/{manifest_id}/revisions/{revision}")
async def builder_manifest_revision_detail(manifest_id: str, revision: int) -> dict[str, Any]:
    try:
        return _dump(builder_service.revision_detail(manifest_id, revision))
    except BuilderManifestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/builder/manifests/{manifest_id}")
async def get_builder_manifest(manifest_id: str) -> dict[str, Any]:
    try:
        return _dump(builder_service.get_manifest(manifest_id))
    except BuilderManifestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
