from __future__ import annotations

from app.ai.models import ExperimentGenerationRequest, ExperimentRefineRequest


class ExperimentPromptBuilder:
    def generation_prompt(self, request: ExperimentGenerationRequest) -> str:
        return "\n".join(
            [
                "Create an ExperimentManifest draft only.",
                "Do not generate code, runtime state, physics engines, or frontend components.",
                f"Description: {request.description}",
                f"Grade: {request.grade}" if request.grade is not None else "Grade: unspecified",
                f"Subject: {request.subject or 'unspecified'}",
                f"Topic: {request.topic or 'unspecified'}",
                f"Difficulty: {request.difficulty or 'easy'}",
            ]
        )

    def refinement_prompt(self, request: ExperimentRefineRequest) -> str:
        return "\n".join(
            [
                "Refine this ExperimentManifest draft only.",
                "Keep the output manifest-driven and runtime-agnostic.",
                f"Instructions: {request.instructions}",
            ]
        )
