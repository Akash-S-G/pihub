from __future__ import annotations

from typing import Any

from app.educational_intelligence.artifact_cleaning import clean_text, sentence_split
from app.educational_intelligence.inference_client import InferenceClient


class ApplicationsGenerator:
    """Generate real-world applications and connections for concepts.

    Uses inference-service AI endpoint as the primary method.
    Falls back to extracting application-related sentences from content.
    """

    def __init__(self, inference_client: InferenceClient | None = None) -> None:
        self.inference = inference_client or InferenceClient()

    async def generate(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        metadata = chunks[0].get("metadata", {}) if chunks else {}
        text_parts: list[str] = []
        concepts: list[str] = []
        for chunk in chunks[:10]:
            t = clean_text(str(chunk.get("text", "")))
            if t:
                text_parts.append(t)
            for c in (chunk.get("metadata", {}).get("concepts") or chunk.get("metadata", {}).get("topics") or []):
                if c not in concepts:
                    concepts.append(c)

        content = "\n\n".join(text_parts)[:8000]
        title = metadata.get("chapter") or "Untitled"

        ai_result = await self.inference.generate_applications(
            title=title,
            content=content,
            concepts=concepts[:20],
            grade=metadata.get("grade"),
            subject=metadata.get("subject"),
            chapter=metadata.get("chapter"),
            language=metadata.get("language"),
        )
        if ai_result and ai_result.get("items"):
            return [
                {
                    "concept": clean_text(str(item.get("concept", ""))),
                    "real_world_use": clean_text(str(item.get("real_world_use", ""))),
                    "explanation": clean_text(str(item.get("explanation", ""))),
                    "language": metadata.get("language", "en"),
                    "generated_by": "inference-service",
                }
                for item in ai_result["items"]
                if clean_text(str(item.get("concept", "")))
            ]

        return self._heuristic_generate(text_parts, concepts)

    def _heuristic_generate(self, text_parts: list[str], concepts: list[str]) -> list[dict[str, Any]]:
        all_text = " ".join(text_parts)
        sentences = sentence_split(all_text)
        applications = []

        app_markers = ["application", "real-world", "example", "for instance", "such as",
                        "used in", "applied to", "in daily life", "in practice"]
        for sentence in sentences:
            lower = sentence.lower()
            for marker in app_markers:
                if marker in lower:
                    applications.append({
                        "concept": concepts[len(applications)] if len(applications) < len(concepts) else "Application",
                        "real_world_use": sentence.strip()[:200],
                        "explanation": sentence.strip()[:200],
                        "generated_by": "heuristic",
                    })
                    break

        if not applications and concepts:
            for concept in concepts[:4]:
                applications.append({
                    "concept": concept,
                    "real_world_use": f"{concept} has practical applications in daily life and technology",
                    "explanation": f"Understanding {concept} helps in solving real-world problems",
                    "generated_by": "heuristic",
                })

        return applications[:6]
