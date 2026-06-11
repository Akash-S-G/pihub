from __future__ import annotations

from typing import Any


class CurriculumEnrichmentMatcher:
    def match(self, topic: str, grade: int | None = None, subject: str | None = None) -> dict[str, Any]:
        topic_l = topic.lower()
        sources = []
        if any(keyword in topic_l for keyword in ["photo", "plant", "chlorophyll", "leaf"]):
            sources = ["NCERT", "Khan Academy", "PhET", "OLabs", "Britannica Kids"]
        elif any(keyword in topic_l for keyword in ["math", "algebra", "geometry", "equation"]):
            sources = ["GeoGebra", "Khan Academy", "NCERT"]
        else:
            sources = ["NCERT", "Khan Academy", "Britannica Kids"]

        return {
            "topic": topic,
            "grade": grade,
            "subject": subject,
            "sources": sources,
        }


class SimulationFinder:
    def find(self, topic: str) -> list[dict[str, Any]]:
        return [
            {
                "type": "simulation",
                "topic": topic,
                "title": f"{topic.title()} simulation",
                "offline_supported": True,
                "interactive": True,
            }
        ]


class ExperimentRetriever:
    def find(self, topic: str) -> list[dict[str, Any]]:
        return [
            {
                "type": "experiment",
                "topic": topic,
                "title": f"{topic.title()} activity",
                "offline_supported": True,
                "interactive": False,
            }
        ]


class EducationalFilter:
    def filter(self, items: list[dict[str, Any]], grade: int | None = None) -> list[dict[str, Any]]:
        filtered = []
        for item in items:
            if item.get("offline_supported", True) is False:
                continue
            if grade is not None and item.get("grade_range") and grade not in item.get("grade_range", []):
                continue
            filtered.append(item)
        return filtered


class EnrichmentRouter:
    """Plan offline-friendly enrichment resources for a topic."""

    def __init__(self) -> None:
        self.matcher = CurriculumEnrichmentMatcher()
        self.simulation_finder = SimulationFinder()
        self.experiment_retriever = ExperimentRetriever()
        self.educational_filter = EducationalFilter()

    def route(self, topic: str, grade: int | None = None, subject: str | None = None) -> dict[str, Any]:
        match = self.matcher.match(topic, grade=grade, subject=subject)
        simulations = self.simulation_finder.find(topic)
        experiments = self.experiment_retriever.find(topic)

        resources = self.educational_filter.filter(
            [
                {
                    "resource_type": "diagram",
                    "topic": topic,
                    "title": f"{topic.title()} diagram",
                    "offline_supported": True,
                    "interactive": False,
                    "source": match["sources"][0],
                    "grade_range": [grade] if grade is not None else [],
                },
                *simulations,
                *experiments,
            ],
            grade=grade,
        )

        return {
            "topic": topic,
            "grade": grade,
            "subject": subject,
            "sources": match["sources"],
            "resources": resources,
        }
