import os
import httpx
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _normalize_language_code(language: str | None) -> str:
    value = str(language or "").strip().lower().replace("_", "-")
    if value.startswith("kn") or value in {"kan", "kannada"}:
        return "kn"
    if value.startswith("hi") or value in {"hin", "hindi"}:
        return "hi"
    if value.startswith("en") or value in {"eng", "english"}:
        return "en"
    return value or "en"

class InferenceTutorAdapter:
    """Adapter to call the tutor endpoint on the inference service."""

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or os.getenv("VOICE_TUTOR_URL") or "http://inference-service:8010").rstrip("/")

    async def get_answer(self, question: str, language: str, session_id: str, simulation_context: dict[str, Any] | None = None) -> str:
        normalized_language = _normalize_language_code(language)
        # Wrap session_id inside session_state so inference service SessionManager finds it
        payload = {
            "question": question,
            "language": normalized_language,
            "session_state": {
                "session_id": session_id
            },
            "simulation_context": simulation_context or {}
        }
        
        url = f"{self.base_url}/ai/tutor"
        logger.info(f"[VOICE] Invoking tutor at {url} with payload: {payload}")
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            
        return str(result.get("answer") or result.get("text") or "")
