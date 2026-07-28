from __future__ import annotations

from typing import Any


class CurriculumEnrichmentMatcher:
    """Match topics to real enrichment resources based on subject and content analysis."""

    RESOURCE_MAP: dict[str, list[dict[str, Any]]] = {
        "photosynthesis": [
            {"type": "simulation", "title": "Photosynthesis Simulation", "source": "PhET", "offline_supported": True},
            {"type": "video", "title": "Photosynthesis Process Video", "source": "Khan Academy", "offline_supported": True},
            {"type": "diagram", "title": "Photosynthesis Diagram", "source": "NCERT", "offline_supported": True},
        ],
        "respiration": [
            {"type": "simulation", "title": "Cellular Respiration Simulation", "source": "PhET", "offline_supported": True},
            {"type": "video", "title": "Respiration Explained", "source": "Khan Academy", "offline_supported": True},
        ],
        "electricity": [
            {"type": "simulation", "title": "Circuit Construction Kit", "source": "PhET", "offline_supported": True},
            {"type": "experiment", "title": "Ohm's Law Experiment", "source": "OLabs", "offline_supported": True},
        ],
        "magnetism": [
            {"type": "simulation", "title": "Magnet and Compass", "source": "PhET", "offline_supported": True},
            {"type": "experiment", "title": "Magnetic Field Mapping", "source": "OLabs", "offline_supported": True},
        ],
        "fraction": [
            {"type": "simulation", "title": "Fraction Matcher", "source": "PhET", "offline_supported": True},
            {"type": "activity", "title": "Fraction Building Activity", "source": "GeoGebra", "offline_supported": True},
        ],
        "geometry": [
            {"type": "tool", "title": "Geometric Constructions", "source": "GeoGebra", "offline_supported": True},
            {"type": "simulation", "title": "Shape Builder", "source": "PhET", "offline_supported": True},
        ],
        "force": [
            {"type": "simulation", "title": "Forces and Motion", "source": "PhET", "offline_supported": True},
            {"type": "experiment", "title": "Force Measurement Lab", "source": "OLabs", "offline_supported": True},
        ],
        "motion": [
            {"type": "simulation", "title": "Moving Man Simulation", "source": "PhET", "offline_supported": True},
            {"type": "video", "title": "Motion Concepts Explained", "source": "Khan Academy", "offline_supported": True},
        ],
        "light": [
            {"type": "simulation", "title": "Bending Light Simulation", "source": "PhET", "offline_supported": True},
            {"type": "experiment", "title": "Reflection and Refraction", "source": "OLabs", "offline_supported": True},
        ],
        "sound": [
            {"type": "simulation", "title": "Sound Waves Simulation", "source": "PhET", "offline_supported": True},
            {"type": "activity", "title": "Sound Wave Activity", "source": "NCERT", "offline_supported": True},
        ],
        "cell": [
            {"type": "diagram", "title": "Cell Structure Diagram", "source": "NCERT", "offline_supported": True},
            {"type": "simulation", "title": "Cell Building Simulation", "source": "PhET", "offline_supported": True},
        ],
        "chemical": [
            {"type": "simulation", "title": "Reactants and Products", "source": "PhET", "offline_supported": True},
            {"type": "experiment", "title": "Chemical Reactions Lab", "source": "OLabs", "offline_supported": True},
        ],
        "plant": [
            {"type": "diagram", "title": "Plant Life Cycle", "source": "NCERT", "offline_supported": True},
            {"type": "activity", "title": "Plant Growth Observation", "source": "NCERT", "offline_supported": True},
        ],
        "human body": [
            {"type": "diagram", "title": "Human Body Systems", "source": "NCERT", "offline_supported": True},
            {"type": "simulation", "title": "Body Systems Interactive", "source": "PhET", "offline_supported": True},
        ],
        "algebra": [
            {"type": "tool", "title": "Algebra Equation Solver", "source": "GeoGebra", "offline_supported": True},
            {"type": "activity", "title": "Algebraic Thinking Practice", "source": "Khan Academy", "offline_supported": True},
        ],
        "trigonometry": [
            {"type": "tool", "title": "Trigonometric Functions", "source": "GeoGebra", "offline_supported": True},
            {"type": "video", "title": "Trigonometry Basics", "source": "Khan Academy", "offline_supported": True},
        ],
        "probability": [
            {"type": "simulation", "title": "Probability Explorer", "source": "PhET", "offline_supported": True},
            {"type": "activity", "title": "Probability Games", "source": "NCERT", "offline_supported": True},
        ],
        "energy": [
            {"type": "simulation", "title": "Energy Forms and Changes", "source": "PhET", "offline_supported": True},
            {"type": "experiment", "title": "Energy Conservation Lab", "source": "OLabs", "offline_supported": True},
        ],
        "water": [
            {"type": "simulation", "title": "Water Cycle Simulation", "source": "PhET", "offline_supported": True},
            {"type": "diagram", "title": "Water Cycle Diagram", "source": "NCERT", "offline_supported": True},
        ],
        "solar": [
            {"type": "simulation", "title": "Solar System Simulation", "source": "PhET", "offline_supported": True},
            {"type": "video", "title": "Solar System Explained", "source": "Khan Academy", "offline_supported": True},
        ],
        "environment": [
            {"type": "activity", "title": "Ecosystem Exploration", "source": "NCERT", "offline_supported": True},
            {"type": "video", "title": "Environmental Science", "source": "Khan Academy", "offline_supported": True},
        ],
    }

    DEFAULT_RESOURCES: list[dict[str, Any]] = [
        {"type": "simulation", "title": "Interactive Simulation", "source": "PhET", "offline_supported": True},
        {"type": "video", "title": "Educational Video", "source": "Khan Academy", "offline_supported": True},
        {"type": "experiment", "title": "Virtual Lab", "source": "OLabs", "offline_supported": True},
        {"type": "diagram", "title": "Reference Diagram", "source": "NCERT", "offline_supported": True},
    ]

    def match(self, topic: str, grade: int | None = None, subject: str | None = None) -> dict[str, Any]:
        topic_l = topic.lower().strip()

        matched_resources: list[dict[str, Any]] = []
        matched_keys: list[str] = []

        for key, resources in self.RESOURCE_MAP.items():
            if key in topic_l or topic_l in key:
                matched_resources.extend(resources)
                matched_keys.append(key)

        sources: list[str] = []
        seen_sources: set[str] = set()
        for resource in matched_resources:
            source = resource.get("source", "")
            if source and source not in seen_sources:
                seen_sources.add(source)
                sources.append(source)

        if not sources:
            if subject:
                subject_l = subject.lower()
                if subject_l in {"science", "physics", "chemistry", "biology"}:
                    sources = ["NCERT", "PhET", "OLabs", "Khan Academy"]
                elif subject_l in {"maths", "mathematics"}:
                    sources = ["NCERT", "GeoGebra", "Khan Academy"]
                elif subject_l in {"social", "social_science", "history", "geography"}:
                    sources = ["NCERT", "Khan Academy"]
                else:
                    sources = ["NCERT", "Khan Academy"]
            else:
                sources = ["NCERT", "Khan Academy"]

        if not matched_resources:
            matched_resources = list(self.DEFAULT_RESOURCES)

        return {
            "topic": topic,
            "grade": grade,
            "subject": subject,
            "matched_concepts": matched_keys,
            "sources": sources,
            "resources": [{
                "resource_type": r["type"],
                "title": r["title"],
                "source": r["source"],
                "offline_supported": r.get("offline_supported", True),
            } for r in matched_resources],
        }


class EnrichmentRouter:
    """Plan offline-friendly enrichment resources for a topic.

    Matches topics to real resources from PhET, OLabs, GeoGebra,
    Khan Academy, and NCERT. Uses keyword-based matching with
    subject-aware fallback.
    """

    def __init__(self) -> None:
        self.matcher = CurriculumEnrichmentMatcher()

    def route(self, topic: str, grade: int | None = None, subject: str | None = None) -> dict[str, Any]:
        return self.matcher.match(topic, grade=grade, subject=subject)
