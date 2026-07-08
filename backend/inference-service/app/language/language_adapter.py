from __future__ import annotations

import re
import time
from typing import Any, Awaitable, Callable

from shared.text_normalization import language_display_name, normalize_language_code

CompletionFn = Callable[[str, str, Any], Awaitable[str]]


class LanguageAdapter:
    """Adapts tutor responses into natural teacher language.

    This is deliberately not a direct translation layer. It asks the same tutor
    model to restate the answer as a teacher speaking to the student.
    """

    SCRIPT_HINTS = {
        "hi": "Use natural Hindi in Devanagari script.",
        "kn": "Use natural Kannada in Kannada script. Preserve code-switched English terms when they are common in the classroom.",
        "en": "Use clear natural English.",
    }

    def detect_language(self, request: Any) -> str:
        explicit = self.normalize(getattr(request, "language", None))
        if explicit:
            return explicit
        question = str(getattr(request, "question", "") or "")
        if re.search(r"[\u0c80-\u0cff]", question):
            return "kn"
        if re.search(r"[\u0900-\u097f]", question):
            return "hi"
        return "en"

    def normalize(self, language: Any) -> str | None:
        if language is None:
            return None
        code = normalize_language_code(str(language))
        return code or None

    def prompt_instruction(self, language: str) -> str:
        language = self.normalize(language) or "en"
        return (
            f"Final answer language: {language_display_name(language)} ({language}). "
            f"{self.SCRIPT_HINTS[language]} "
            "Do not translate word-for-word; explain naturally as a helpful teacher. "
            "Preserve important technical terms and mixed-language classroom phrasing when appropriate."
        )

    async def adapt(self, answer: str, target_language: str, request: Any, completion: CompletionFn) -> tuple[str, float]:
        started = time.perf_counter()
        language = self.normalize(target_language) or "en"
        if language == "en":
            return answer, (time.perf_counter() - started) * 1000

        system_prompt = (
            "You are a multilingual school tutor. Rewrite the answer for the student in the target language. "
            "Keep the meaning faithful to the educational answer and preserve formulas, numbers, and key terms when useful. "
            "If the answer already contains code-switched terms or local names, keep them natural instead of translating everything. "
            "Do not add new facts."
        )
        user_prompt = (
            f"Target language: {language_display_name(language)} ({language})\n"
            f"{self.SCRIPT_HINTS[language]}\n\n"
            f"Student question:\n{getattr(request, 'question', '')}\n\n"
            f"Educational answer to adapt:\n{answer}\n\n"
            "Return only the adapted answer."
        )
        adapted = await completion(system_prompt, user_prompt, request)
        return adapted.strip() or answer, (time.perf_counter() - started) * 1000
