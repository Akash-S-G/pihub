from __future__ import annotations

import json
from pathlib import Path

from app.content_generation import DoclingPdfExtractor, GemmaArtifactGenerator, SectionBuilder


BENCHMARKS = [
    {
        "name": "grade8_science",
        "metadata": {"grade": 8, "subject": "science", "chapter": "Force and Pressure", "language": "english"},
        "text": """
Force and Pressure

Force is a push or pull acting on an object. A force can change the speed, direction, or shape of an object.
Pressure is the force acting per unit area. Pressure = Force / Area. When the same force acts on a smaller
area, the pressure is greater. For example, a sharp nail enters wood more easily than a blunt nail because
the sharp tip has a smaller area and therefore produces greater pressure.

Fluids also exert pressure. Air pressure acts in all directions. Students should remember that pressure
depends on both force and area, not force alone.
""",
    },
    {
        "name": "grade9_mathematics",
        "metadata": {"grade": 9, "subject": "mathematics", "chapter": "Linear Equations", "language": "english"},
        "text": """
Linear Equations in Two Variables

A linear equation in two variables is an equation that can be written as ax + by + c = 0, where a, b, and c
are real numbers and a and b are not both zero. Each solution is an ordered pair. The graph of a linear
equation in two variables is a straight line.

For example, x + y = 5 has solutions such as (1, 4), (2, 3), and (5, 0). These points lie on the same line.
""",
    },
    {
        "name": "grade10_biology",
        "metadata": {"grade": 10, "subject": "biology", "chapter": "Life Processes", "language": "english"},
        "text": """
Life Processes

Photosynthesis is the process by which green plants prepare food using carbon dioxide, water, and sunlight.
Chlorophyll captures light energy. The word equation is carbon dioxide + water -> glucose + oxygen.
This process is important because it provides food for plants and releases oxygen into the atmosphere.

Respiration releases energy from food. Plants and animals both respire, but only green plants perform
photosynthesis.
""",
    },
]


def main() -> None:
    extractor = DoclingPdfExtractor()
    builder = SectionBuilder(min_words=80, max_words=250)
    generator = GemmaArtifactGenerator(inference_url="http://127.0.0.1:0", timeout=0.2)
    results = []
    for benchmark in BENCHMARKS:
        document = extractor.extract_text(benchmark["text"], source_path=benchmark["name"], metadata=benchmark["metadata"])
        sections = builder.build(document)
        artifacts = generator.generate(sections, benchmark["metadata"])
        results.append(
            {
                "benchmark": benchmark["name"],
                "sections": len(sections),
                "summary_valid": bool(artifacts["summaries"]),
                "flashcards": len(artifacts["flashcards"]),
                "quizzes": len(artifacts["quizzes"]),
                "glossary": len(artifacts["glossary"]),
                "learning_objectives": len(artifacts["learning_objectives"]),
                "json_validity": all(
                    [
                        isinstance(artifacts["summaries"], list),
                        isinstance(artifacts["flashcards"], list),
                        isinstance(artifacts["quizzes"], list),
                        isinstance(artifacts["glossary"], list),
                    ]
                ),
            }
        )

    report = {
        "benchmarks": results,
        "overall_json_validity": all(item["json_validity"] for item in results),
        "artifact_coverage": {
            "summary": sum(1 for item in results if item["summary_valid"]),
            "flashcards": sum(1 for item in results if item["flashcards"] > 0),
            "quizzes": sum(1 for item in results if item["quizzes"] > 0),
            "glossary": sum(1 for item in results if item["glossary"] > 0),
            "learning_objectives": sum(1 for item in results if item["learning_objectives"] > 0),
        },
    }
    Path("CONTENT_QUALITY_1_BENCHMARK_REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
