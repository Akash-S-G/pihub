"""Build prelinked educational enrichment registry."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class EnrichmentRegistry:
    """Registry of prelinked educational enrichment resources."""

    def __init__(self):
        """Initialize enrichment registry."""
        self.registry: Dict = {
            "metadata": {
                "version": "1.0.0",
                "created_at": None,
                "total_mappings": 0,
            },
            "simulations": [],
            "experiments": [],
            "videos": [],
            "virtual_labs": [],
            "animations": [],
            "concept_mappings": {},
        }

    def add_phet_simulation(
        self,
        name: str,
        url: str,
        description: str,
        topics: List[str],
        grade_range: tuple = None,
        subject: str = None,
    ) -> None:
        """
        Add PhET simulation to registry.

        Args:
            name: Simulation name
            url: PhET URL
            description: Description
            topics: List of curriculum topics
            grade_range: (min_grade, max_grade)
            subject: Subject area
        """
        sim = {
            "name": name,
            "url": url,
            "description": description,
            "type": "phet_simulation",
            "topics": topics,
            "grade_range": grade_range,
            "subject": subject,
        }

        self.registry["simulations"].append(sim)

        # Add to concept mappings
        for topic in topics:
            if topic not in self.registry["concept_mappings"]:
                self.registry["concept_mappings"][topic] = {
                    "simulations": [],
                    "experiments": [],
                    "videos": [],
                    "virtual_labs": [],
                    "animations": [],
                }

            self.registry["concept_mappings"][topic]["simulations"].append(name)

    def add_experiment(
        self,
        name: str,
        description: str,
        materials: List[str],
        procedure: List[str],
        topics: List[str],
        grade_range: tuple = None,
        subject: str = None,
    ) -> None:
        """
        Add experiment to registry.

        Args:
            name: Experiment name
            description: Description
            materials: List of required materials
            procedure: Step-by-step procedure
            topics: Curriculum topics
            grade_range: (min_grade, max_grade)
            subject: Subject area
        """
        exp = {
            "name": name,
            "description": description,
            "materials": materials,
            "procedure": procedure,
            "type": "experiment",
            "topics": topics,
            "grade_range": grade_range,
            "subject": subject,
        }

        self.registry["experiments"].append(exp)

        # Add to concept mappings
        for topic in topics:
            if topic not in self.registry["concept_mappings"]:
                self.registry["concept_mappings"][topic] = {
                    "simulations": [],
                    "experiments": [],
                    "videos": [],
                    "virtual_labs": [],
                    "animations": [],
                }

            self.registry["concept_mappings"][topic]["experiments"].append(name)

    def add_video(
        self,
        name: str,
        url: str,
        duration_seconds: int,
        description: str,
        topics: List[str],
        source: str = "youtube",
        grade_range: tuple = None,
        subject: str = None,
    ) -> None:
        """
        Add educational video to registry.

        Args:
            name: Video name/title
            url: Video URL
            duration_seconds: Duration in seconds
            description: Description
            topics: Curriculum topics
            source: Video source (youtube, khan_academy, etc.)
            grade_range: (min_grade, max_grade)
            subject: Subject area
        """
        video = {
            "name": name,
            "url": url,
            "duration_seconds": duration_seconds,
            "description": description,
            "type": "video",
            "source": source,
            "topics": topics,
            "grade_range": grade_range,
            "subject": subject,
        }

        self.registry["videos"].append(video)

        # Add to concept mappings
        for topic in topics:
            if topic not in self.registry["concept_mappings"]:
                self.registry["concept_mappings"][topic] = {
                    "simulations": [],
                    "experiments": [],
                    "videos": [],
                    "virtual_labs": [],
                    "animations": [],
                }

            self.registry["concept_mappings"][topic]["videos"].append(name)

    def add_virtual_lab(
        self,
        name: str,
        url: str,
        description: str,
        topics: List[str],
        grade_range: tuple = None,
        subject: str = None,
    ) -> None:
        """
        Add virtual lab to registry.

        Args:
            name: Lab name
            url: Lab URL
            description: Description
            topics: Curriculum topics
            grade_range: (min_grade, max_grade)
            subject: Subject area
        """
        lab = {
            "name": name,
            "url": url,
            "description": description,
            "type": "virtual_lab",
            "topics": topics,
            "grade_range": grade_range,
            "subject": subject,
        }

        self.registry["virtual_labs"].append(lab)

        # Add to concept mappings
        for topic in topics:
            if topic not in self.registry["concept_mappings"]:
                self.registry["concept_mappings"][topic] = {
                    "simulations": [],
                    "experiments": [],
                    "videos": [],
                    "virtual_labs": [],
                    "animations": [],
                }

            self.registry["concept_mappings"][topic]["virtual_labs"].append(name)

    def add_animation(
        self,
        name: str,
        url: str,
        description: str,
        topics: List[str],
        file_format: str = "mp4",
        grade_range: tuple = None,
        subject: str = None,
    ) -> None:
        """
        Add animation to registry.

        Args:
            name: Animation name
            url: Animation URL
            description: Description
            topics: Curriculum topics
            file_format: File format (mp4, webm, svg, etc.)
            grade_range: (min_grade, max_grade)
            subject: Subject area
        """
        anim = {
            "name": name,
            "url": url,
            "description": description,
            "type": "animation",
            "file_format": file_format,
            "topics": topics,
            "grade_range": grade_range,
            "subject": subject,
        }

        self.registry["animations"].append(anim)

        # Add to concept mappings
        for topic in topics:
            if topic not in self.registry["concept_mappings"]:
                self.registry["concept_mappings"][topic] = {
                    "simulations": [],
                    "experiments": [],
                    "videos": [],
                    "virtual_labs": [],
                    "animations": [],
                }

            self.registry["concept_mappings"][topic]["animations"].append(name)

    def get_enrichment_for_concept(self, concept: str) -> Dict:
        """
        Get all enrichment resources for a concept.

        Args:
            concept: Curriculum concept/topic

        Returns:
            Dictionary with enrichment resources
        """
        return self.registry["concept_mappings"].get(concept, {})

    def finalize(self) -> Dict:
        """
        Finalize registry with metadata.

        Returns:
            Finalized registry
        """
        from datetime import datetime

        self.registry["metadata"]["created_at"] = datetime.utcnow().isoformat()
        self.registry["metadata"]["total_mappings"] = len(self.registry["concept_mappings"])
        self.registry["metadata"]["total_simulations"] = len(self.registry["simulations"])
        self.registry["metadata"]["total_experiments"] = len(self.registry["experiments"])
        self.registry["metadata"]["total_videos"] = len(self.registry["videos"])
        self.registry["metadata"]["total_virtual_labs"] = len(self.registry["virtual_labs"])
        self.registry["metadata"]["total_animations"] = len(self.registry["animations"])

        return self.registry

    def save(self, output_path: Path) -> None:
        """
        Save registry to JSON.

        Args:
            output_path: Path to save registry
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self.finalize()

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.registry, f, indent=2)

        logger.info(f"Enrichment registry saved to {output_path}")

    @staticmethod
    def load(path: Path) -> "EnrichmentRegistry":
        """
        Load registry from JSON.

        Args:
            path: Path to registry file

        Returns:
            Loaded registry
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        registry = EnrichmentRegistry()
        registry.registry = data

        return registry


def create_default_enrichment_registry() -> EnrichmentRegistry:
    """
    Create default enrichment registry with curated resources.

    Returns:
        Enrichment registry with default resources
    """
    registry = EnrichmentRegistry()

    # Add PhET simulations
    registry.add_phet_simulation(
        name="Waves Intro",
        url="https://phet.colorado.edu/en/simulations/filter?subjects=physics&types=html,prototype",
        description="Explore properties of waves",
        topics=["waves", "sound", "light"],
        grade_range=(6, 10),
        subject="science",
    )

    registry.add_phet_simulation(
        name="Circuit Construction Kit",
        url="https://phet.colorado.edu/en/simulations/filter?subjects=physics",
        description="Build and analyze circuits",
        topics=["electricity", "circuits", "current"],
        grade_range=(8, 10),
        subject="science",
    )

    registry.add_phet_simulation(
        name="Protein Folding",
        url="https://phet.colorado.edu/en/simulations/filter?subjects=biology",
        description="Understand protein structure and folding",
        topics=["protein synthesis", "biology", "cell biology"],
        grade_range=(8, 10),
        subject="science",
    )

    # Add experiments
    registry.add_experiment(
        name="Photosynthesis Experiment",
        description="Demonstrate photosynthesis using elodea plant",
        materials=["water plant", "test tube", "light source", "sodium bicarbonate"],
        procedure=[
            "Place aquatic plant in water with sodium bicarbonate",
            "Expose to light",
            "Observe oxygen bubbles",
            "Compare with dark conditions",
        ],
        topics=["photosynthesis", "plant biology", "oxygen production"],
        grade_range=(6, 8),
        subject="science",
    )

    registry.add_experiment(
        name="Acid-Base Indicators",
        description="Create natural pH indicators from red cabbage",
        materials=["red cabbage", "acids", "bases", "test tubes"],
        procedure=[
            "Chop red cabbage",
            "Boil in water",
            "Use extract as pH indicator",
            "Test with various acids and bases",
        ],
        topics=["acids and bases", "pH", "chemistry", "indicators"],
        grade_range=(8, 10),
        subject="science",
    )

    # Add videos
    registry.add_video(
        name="Quadratic Equations Explained",
        url="https://www.youtube.com/results?search_query=quadratic+equations",
        duration_seconds=600,
        description="Complete explanation of quadratic equations and solutions",
        topics=["quadratic equations", "algebra", "polynomials"],
        source="youtube",
        grade_range=(9, 10),
        subject="mathematics",
    )

    registry.add_video(
        name="Introduction to Trigonometry",
        url="https://www.youtube.com/results?search_query=trigonometry+introduction",
        duration_seconds=900,
        description="Learn trigonometric ratios and functions",
        topics=["trigonometry", "sine", "cosine", "tangent"],
        source="youtube",
        grade_range=(9, 10),
        subject="mathematics",
    )

    # Add virtual labs
    registry.add_virtual_lab(
        name="Plant Anatomy Virtual Lab",
        url="https://www.biologyonline.org/",
        description="Explore plant cell structure and tissues",
        topics=["plant biology", "cell structure", "tissues"],
        grade_range=(7, 9),
        subject="science",
    )

    registry.add_virtual_lab(
        name="Chemistry Virtual Lab",
        url="https://www.chemistrylearning.com/",
        description="Perform chemistry experiments safely online",
        topics=["chemistry", "reactions", "states of matter"],
        grade_range=(8, 10),
        subject="science",
    )

    # Add animations
    registry.add_animation(
        name="Water Cycle Animation",
        url="https://www.example.com/water-cycle.mp4",
        description="Animated visualization of the water cycle",
        topics=["water cycle", "evaporation", "condensation", "precipitation"],
        file_format="mp4",
        grade_range=(5, 7),
        subject="science",
    )

    registry.add_animation(
        name="Solar System Motion",
        url="https://www.example.com/solar-system.mp4",
        description="Animation of planetary motion around the sun",
        topics=["solar system", "planets", "orbits", "astronomy"],
        file_format="mp4",
        grade_range=(6, 8),
        subject="science",
    )

    return registry
