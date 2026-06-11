from __future__ import annotations

from app.content_pipeline.educational_chunker import EducationalChunkerV2


def main() -> None:
    sample = """
Chapter 1: Nutrition in Plants

Definition: Photosynthesis is the process by which green plants prepare food.

Formula: 6CO2 + 6H2O -> C6H12O6 + 6O2

Example: Leaves appear green because chlorophyll reflects green wavelengths.

Experiment: Place one plant in sunlight and one in darkness for 24 hours.
Observation: The leaf in sunlight turns blue-black with iodine.

Q: Why are leaves green?
A: Due to chlorophyll pigment.
"""

    chunker = EducationalChunkerV2()
    chunks = chunker.chunk_educational(sample, {"grade": 7, "subject": "science", "chapter": "Nutrition in Plants"})
    print(f"chunks={len(chunks)}")
    for i, chunk in enumerate(chunks, start=1):
        print(f"[{i}] type={chunk['metadata'].get('chunk_type')} section={chunk['metadata'].get('section')}")


if __name__ == "__main__":
    main()
