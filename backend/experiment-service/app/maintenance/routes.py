from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.maintenance.services import (
    ClassroomConsistencyService,
    DatabaseMaintenanceService,
    HashAuditService,
    IntegrityScanner,
)


router = APIRouter(tags=["Experiment Maintenance"])


@router.get("/maintenance/database-health")
async def database_health() -> dict[str, Any]:
    return DatabaseMaintenanceService().health()


@router.get("/maintenance/hash-audit")
async def hash_audit() -> dict[str, Any]:
    return HashAuditService().audit()


@router.get("/maintenance/storage-stats")
async def storage_stats() -> dict[str, Any]:
    service = DatabaseMaintenanceService()
    return {
        "database_health": service.health(),
    }


@router.get("/maintenance/classroom-health")
async def classroom_health() -> dict[str, Any]:
    return ClassroomConsistencyService().health()


@router.get("/maintenance/system-integrity")
async def system_integrity() -> dict[str, Any]:
    return {
        "hash_audit": HashAuditService().audit(),
        "orphan_scan": IntegrityScanner().scan(),
        "database_health": DatabaseMaintenanceService().health(),
        "classroom_health": ClassroomConsistencyService().health(),
    }
