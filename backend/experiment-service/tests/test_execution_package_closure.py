from __future__ import annotations

import pytest

pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from app.main import app
from app.manifest import routes as manifest_routes
from app.manifest.manifest_service import ExperimentManifestService
from app.models.manifest_storage import CreateBuilderManifestRequest
from app.services.execution_package_service import ExecutionPackageService
from app.services.manifest_resolver import ManifestResolver
from app.services.manifest_storage_service import ManifestStorageService
from app.storage.manifest_storage_repository import ManifestStorageRepository


def _manifest(label: str) -> dict:
    variables = [
        {
            "name": "length",
            "type": "number",
            "default_value": 1.0,
            "min_value": 0.1,
            "max_value": 2.0,
            "unit": "m",
            "description": "String length",
        }
    ]
    objects = [
        {
            "object_id": f"{label}-object",
            "object_type": "sphere",
            "name": "Pendulum Bob",
            "properties": {},
            "metadata": {},
        }
    ]
    rules = [
        {
            "rule_id": f"{label}-record",
            "name": "Record Observation",
            "trigger": "observation_added",
            "condition": {},
            "action": {"type": "record_observation"},
            "enabled": True,
        }
    ]
    scene = {
        "scene_id": f"{label}-scene",
        "name": "Pendulum Scene",
        "description": "Observe pendulum motion.",
        "objects": objects,
        "variables": variables,
        "rules": rules,
        "metadata": {},
    }
    execution = {
        "supported_modes": ["observation", "simulation"],
        "required_sensors": [],
        "scene": scene,
        "variables": variables,
        "objects": objects,
        "rules": rules,
    }
    return {
        "manifest_version": "1.0.0",
        "id": f"{label}-manifest",
        "title": f"{label.title()} Manifest",
        "description": "Teacher-created execution package test manifest.",
        "subject": "Physics",
        "grade": 7,
        "chapter": "Motion",
        "topic": "Pendulum Motion",
        "difficulty": "easy",
        "supported_modes": ["observation", "simulation"],
        "required_sensors": [],
        "estimated_duration_minutes": 20,
        "tags": ["test"],
        "variables": variables,
        "objects": objects,
        "rules": rules,
        "scene": scene,
        "execution": execution,
        "metadata": {"source": "test"},
    }


def _service(tmp_path):
    repository = ManifestStorageRepository(tmp_path / "builder.sqlite3")
    manifest_service = ExperimentManifestService()
    storage_service = ManifestStorageService(repository=repository)
    package_service = ExecutionPackageService(
        manifest_service=manifest_service,
        manifest_resolver=ManifestResolver(manifest_service, repository),
    )
    manifest_routes.execution_package_service = package_service
    return storage_service


def _create_published(storage_service: ManifestStorageService, label: str) -> str:
    created = storage_service.create_draft(
        CreateBuilderManifestRequest(
            owner_id="teacher_test",
            title=f"{label.title()} Manifest",
            manifest=_manifest(label),
        )
    )
    storage_service.publish(created.manifest_id)
    return created.manifest_id


def test_execution_package_template_manifest(tmp_path):
    _service(tmp_path)
    template = ExperimentManifestService().list_templates()[0]
    response = TestClient(app).post("/execution-package", json={"manifest_id": template.template_id})
    assert response.status_code == 200
    payload = response.json()
    assert payload["supported"] is True
    assert payload["metadata"]["source"] == "template"


def test_execution_package_published_builder_manifest(tmp_path):
    storage_service = _service(tmp_path)
    manifest_id = _create_published(storage_service, "published")
    response = TestClient(app).post("/execution-package", json={"manifest_id": manifest_id})
    assert response.status_code == 200
    payload = response.json()
    assert payload["supported"] is True
    assert payload["metadata"]["source"] == "builder"
    assert payload["metadata"]["revision"] == 1
    assert payload["metadata"]["manifest_hash"]
    assert payload["metadata"]["revision_hash"]


def test_execution_package_missing_manifest(tmp_path):
    _service(tmp_path)
    response = TestClient(app).post("/execution-package", json={"manifest_id": "missing"})
    assert response.status_code == 404


def test_execution_package_archived_manifest(tmp_path):
    storage_service = _service(tmp_path)
    manifest_id = _create_published(storage_service, "archived")
    storage_service.archive(manifest_id)
    response = TestClient(app).post("/execution-package", json={"manifest_id": manifest_id})
    assert response.status_code == 409


def test_execution_package_invalid_revision(tmp_path):
    storage_service = _service(tmp_path)
    manifest_id = _create_published(storage_service, "revision")
    response = TestClient(app).post("/execution-package", json={"manifest_id": manifest_id, "revision": 99})
    assert response.status_code == 404
