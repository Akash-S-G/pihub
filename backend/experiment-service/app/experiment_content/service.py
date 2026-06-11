from __future__ import annotations

import io
import json
import re
import tarfile
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from app.experiment_content.models import (
    ChapterExperimentMapping,
    ExperimentCatalogItem,
    ExperimentCertification,
    ExperimentLearningContent,
    ExperimentPackage,
)
from app.manifest.manifest_service import ExperimentManifestService


def _dump_model(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


def _slug(value: str) -> str:
    normalized = value.lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    return re.sub(r"_+", "_", normalized).strip("_")


class ExperimentContentService:
    """Build content-only experiment catalog artifacts from certified manifests."""

    def __init__(self, manifest_service: ExperimentManifestService | None = None) -> None:
        self.manifest_service = manifest_service or ExperimentManifestService()

    def catalog(self) -> list[dict[str, Any]]:
        items = [self.catalog_item(template.manifest) for template in self.manifest_service.list_templates()]
        return [_dump_model(item) for item in items if self.certification(item.id).certified]

    def experiment(self, experiment_id: str) -> dict[str, Any]:
        manifest = self._manifest(experiment_id)
        package = self.package(experiment_id)
        return {
            **_dump_model(self.catalog_item(manifest)),
            "manifest": manifest,
            "metadata": package.metadata,
            "learning_content": _dump_model(package.learning_content),
            "flashcards": package.flashcards,
            "quiz": package.quiz,
            "glossary": package.glossary,
            "summary": package.summary,
            "certification": _dump_model(package.certification),
            "download_url": f"/experiments/{experiment_id}/download",
        }

    def package(self, experiment_id: str) -> ExperimentPackage:
        manifest = self._manifest(experiment_id)
        learning_content = self.learning_content(manifest)
        certification = self.certification(experiment_id)
        return ExperimentPackage(
            manifest=manifest,
            metadata=self.metadata(manifest),
            learning_content=learning_content,
            questions=self.questions(manifest, learning_content),
            observations=self.observations(manifest),
            flashcards=self.flashcards(manifest, learning_content),
            quiz=self.quiz(manifest, learning_content),
            glossary=self.glossary(manifest, learning_content),
            summary=self.summary(manifest, learning_content),
            certification=certification,
        )

    def package_bytes(self, experiment_id: str) -> bytes:
        package = self.package(experiment_id)
        payloads = {
            "manifest.json": package.manifest,
            "metadata.json": package.metadata,
            "learning_content.json": _dump_model(package.learning_content),
            "questions.json": package.questions,
            "observations.json": package.observations,
            "flashcards.json": package.flashcards,
            "quiz.json": package.quiz,
            "glossary.json": package.glossary,
            "summary.json": package.summary,
            "certification.json": _dump_model(package.certification),
        }
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            for name, payload in payloads.items():
                data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mtime = int(datetime.now(tz=timezone.utc).timestamp())
                archive.addfile(info, io.BytesIO(data))
        return buffer.getvalue()

    def certification(self, experiment_id: str) -> ExperimentCertification:
        manifest = self._manifest(experiment_id)
        execution = manifest.get("execution") if isinstance(manifest.get("execution"), dict) else {}
        checks = {
            "manifest_valid": self.manifest_service.validate(manifest).valid,
            "objects_valid": bool(execution.get("objects")),
            "variables_valid": bool(execution.get("variables")),
            "rules_valid": bool(execution.get("rules")),
            "runtime_profile_valid": self.runtime_profile(manifest) in {"physics", "chemistry", "biology", "mathematics", "observation"},
        }
        errors = [name for name, valid in checks.items() if not valid]
        return ExperimentCertification(
            experiment_id=str(manifest.get("id") or experiment_id),
            certified=all(checks.values()),
            checks=checks,
            errors=errors,
            runtime_profile=self.runtime_profile(manifest),
        )

    def chapter_experiments(self, chapter_id: str) -> dict[str, Any]:
        normalized = _slug(chapter_id)
        matches: list[str] = []
        mapping_chapter = chapter_id
        grade: int | None = None
        subject: str | None = None
        for item in self.catalog():
            manifest = self._manifest(str(item["id"]))
            chapter = str(manifest.get("chapter") or "")
            topic = str(manifest.get("topic") or "")
            candidates = {_slug(chapter), _slug(topic), _slug(str(manifest.get("id") or ""))}
            if normalized in candidates or normalized in _slug(f"{chapter} {topic}"):
                matches.append(str(item["id"]))
                mapping_chapter = chapter or mapping_chapter
                grade = manifest.get("grade")
                subject = self._subject(manifest)
        return _dump_model(
            ChapterExperimentMapping(
                chapter_id=normalized,
                grade=grade,
                subject=subject,
                chapter=mapping_chapter,
                experiments=matches,
            )
        )

    def catalog_item(self, manifest: dict[str, Any]) -> ExperimentCatalogItem:
        return ExperimentCatalogItem(
            id=str(manifest.get("id") or ""),
            title=str(manifest.get("title") or ""),
            subject=self._subject(manifest),
            topics=self._topics(manifest),
            difficulty=self._difficulty(manifest),
            learning_objectives=self._objectives(manifest),
            runtime_profile=self.runtime_profile(manifest),
        )

    def metadata(self, manifest: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": manifest.get("id"),
            "title": manifest.get("title"),
            "subject": self._subject(manifest),
            "grade": manifest.get("grade"),
            "chapter": manifest.get("chapter"),
            "topics": self._topics(manifest),
            "difficulty": self._difficulty(manifest),
            "runtime_profile": self.runtime_profile(manifest),
            "duration_minutes": manifest.get("estimated_duration_minutes"),
            "required_sensors": manifest.get("required_sensors", []),
            "supported_modes": manifest.get("supported_modes", []),
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "server_runtime_execution": False,
        }

    def learning_content(self, manifest: dict[str, Any]) -> ExperimentLearningContent:
        title = str(manifest.get("title") or "Experiment")
        topic = str(manifest.get("topic") or title)
        subject = self._subject(manifest)
        objectives = self._objectives(manifest)
        steps = manifest.get("steps") if isinstance(manifest.get("steps"), list) else []
        procedure = [str(step.get("description") or step.get("title")) for step in steps if isinstance(step, dict)]
        if not procedure:
            procedure = [
                "Set up the experiment using the listed objects and variables.",
                "Change one variable at a time and observe what happens.",
                "Record observations carefully before drawing conclusions.",
            ]
        theory = self._theory(title, topic, subject)
        return ExperimentLearningContent(
            overview=f"{title} helps learners investigate {topic} through a safe, offline, manifest-driven experiment.",
            learning_objectives=objectives,
            theory=theory,
            procedure=procedure,
            expected_results=[
                f"Learners observe how {topic} changes when experimental variables are adjusted.",
                "Measurements and observations support a clear conclusion.",
            ],
            common_mistakes=[
                "Changing more than one variable at a time.",
                "Recording observations without units or context.",
                "Treating one trial as enough evidence for a conclusion.",
            ],
            real_world_applications=self._applications(topic, subject),
        )

    def questions(self, manifest: dict[str, Any], content: ExperimentLearningContent) -> list[dict[str, Any]]:
        topic = str(manifest.get("topic") or manifest.get("title") or "this experiment")
        return [
            {"question": f"What variable is being investigated in {topic}?", "expected_answer": "Identify the independent and dependent variables before starting."},
            {"question": "Why should observations be recorded after every trial?", "expected_answer": "Repeated observations make the conclusion more reliable."},
            {"question": f"What result would support the main idea of {topic}?", "expected_answer": content.expected_results[0]},
        ]

    def observations(self, manifest: dict[str, Any]) -> list[dict[str, Any]]:
        variables = manifest.get("variables") if isinstance(manifest.get("variables"), list) else []
        return [
            {
                "field": str(variable.get("name") or "measurement"),
                "type": str(variable.get("type") or "number"),
                "unit": variable.get("unit"),
                "required": True,
            }
            for variable in variables
            if isinstance(variable, dict)
        ] or [{"field": "observation", "type": "text", "required": True}]

    def flashcards(self, manifest: dict[str, Any], content: ExperimentLearningContent) -> list[dict[str, str]]:
        topic = str(manifest.get("topic") or manifest.get("title") or "Experiment")
        return [
            {"front": f"What is the purpose of {manifest.get('title')}?", "back": content.overview},
            {"front": f"What should be controlled in {topic}?", "back": "Keep all variables constant except the one being tested."},
            {"front": "Why are repeated trials useful?", "back": "Repeated trials reduce error and make the conclusion more reliable."},
        ]

    def quiz(self, manifest: dict[str, Any], content: ExperimentLearningContent) -> list[dict[str, Any]]:
        title = str(manifest.get("title") or "Experiment")
        return [
            {
                "question": f"What is the best first step before running {title}?",
                "options": [
                    {"label": "A", "text": "Identify variables and prepare observations"},
                    {"label": "B", "text": "Change every variable at once"},
                    {"label": "C", "text": "Skip measurement units"},
                    {"label": "D", "text": "Write the conclusion before observing"},
                ],
                "correct_answer": "A",
                "explanation": "A reliable experiment starts by identifying variables and planning observations.",
            },
            {
                "question": "Why should only one variable be changed at a time?",
                "options": [
                    {"label": "A", "text": "It makes the cause of the result easier to identify"},
                    {"label": "B", "text": "It removes the need for observations"},
                    {"label": "C", "text": "It makes the experiment run on the server"},
                    {"label": "D", "text": "It prevents learners from using measurements"},
                ],
                "correct_answer": "A",
                "explanation": "Changing one variable at a time helps connect cause and effect.",
            },
        ]

    def glossary(self, manifest: dict[str, Any], content: ExperimentLearningContent) -> list[dict[str, str]]:
        topic = str(manifest.get("topic") or manifest.get("title") or "Experiment")
        return [
            {"term": topic, "definition": content.theory[:220]},
            {"term": "Variable", "definition": "A factor that can be changed, measured, or controlled in an experiment."},
            {"term": "Observation", "definition": "A careful record of what happens during an experiment."},
        ]

    def summary(self, manifest: dict[str, Any], content: ExperimentLearningContent) -> dict[str, str]:
        return {
            "title": str(manifest.get("title") or "Experiment"),
            "text": f"{content.overview} {content.theory} Learners follow the procedure, record observations, avoid common mistakes, and compare results with expected outcomes.",
        }

    def runtime_profile(self, manifest: dict[str, Any]) -> str:
        raw_subject = str(manifest.get("subject") or "science").strip().lower().replace(" ", "_")
        if raw_subject in {"physics", "chemistry", "biology"}:
            return raw_subject
        subject = self._subject(manifest)
        if subject == "science":
            return "physics"
        if subject in {"maths", "mathematics"}:
            return "mathematics"
        return "observation"

    def _manifest(self, experiment_id: str) -> dict[str, Any]:
        for template in self.manifest_service.list_templates():
            manifest = dict(template.manifest)
            template_ids = {str(template.template_id), str(manifest.get("id") or "")}
            if experiment_id in template_ids:
                return manifest
        raise HTTPException(status_code=404, detail="Experiment not found")

    @staticmethod
    def _subject(manifest: dict[str, Any]) -> str:
        value = str(manifest.get("subject") or "science").strip().lower().replace(" ", "_")
        if value in {"physics", "biology", "chemistry"}:
            return "science"
        return value

    @staticmethod
    def _difficulty(manifest: dict[str, Any]) -> str:
        value = str(manifest.get("difficulty") or "beginner").lower()
        return {"easy": "beginner", "medium": "intermediate", "hard": "advanced"}.get(value, value)

    @staticmethod
    def _topics(manifest: dict[str, Any]) -> list[str]:
        values = [manifest.get("topic"), *(manifest.get("tags") or [])]
        topics = []
        seen = set()
        for value in values:
            text = str(value or "").strip().lower().replace(" ", "_")
            if text and text not in seen:
                topics.append(text)
                seen.add(text)
        return topics

    @staticmethod
    def _objectives(manifest: dict[str, Any]) -> list[str]:
        topic = str(manifest.get("topic") or manifest.get("title") or "the experiment")
        title = str(manifest.get("title") or "Experiment")
        return [
            f"Explain the key idea behind {topic}.",
            f"Identify variables and observations in {title}.",
            "Use observations to form an evidence-based conclusion.",
        ]

    @staticmethod
    def _theory(title: str, topic: str, subject: str) -> str:
        subject_context = {
            "physics": "Physics experiments connect measurements with patterns in motion, force, light, electricity, or matter.",
            "science": "Science experiments use observations and measurements to explain natural phenomena.",
            "biology": "Biology experiments study living systems by comparing growth, structure, or behavior.",
            "mathematics": "Mathematics experiments use representations and repeated trials to reveal patterns.",
        }.get(subject, "Experiments use controlled observations to test an idea.")
        return f"{subject_context} In {title}, learners focus on {topic}, compare variables, and use evidence to explain the result."

    @staticmethod
    def _applications(topic: str, subject: str) -> list[str]:
        if subject in {"physics", "science"}:
            return ["engineering", "transportation", "measurement", "classroom investigations"]
        if subject == "biology":
            return ["agriculture", "environmental monitoring", "health science", "school gardens"]
        return [topic, "problem solving", "data interpretation", "classroom projects"]
