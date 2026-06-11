from __future__ import annotations

import hashlib
import logging
import os
from typing import Any

from .models import StructuredSection


logger = logging.getLogger(__name__)


class GemmaArtifactGenerator:
    """Generate existing pack artifacts from bounded sections through inference-service."""

    def __init__(self, inference_url: str | None = None, timeout: float = 180.0) -> None:
        self.inference_url = (inference_url or os.getenv("INFERENCE_SERVICE_URL", "http://inference-service:8010")).rstrip("/")
        self.timeout = timeout
        self._cache: dict[tuple[str, str], Any] = {}

    def generate(self, sections: list[StructuredSection], metadata: dict[str, Any]) -> dict[str, Any]:
        summaries: list[dict[str, Any]] = []
        flashcards: list[dict[str, Any]] = []
        quizzes: list[dict[str, Any]] = []
        glossary_by_term: dict[str, dict[str, Any]] = {}
        objectives: list[dict[str, Any]] = []

        try:
            import httpx
        except Exception as exc:
            logger.warning("Gemma artifact generation disabled because httpx is unavailable: %s", exc)
            return self._fallback_all(sections)

        with httpx.Client(timeout=self.timeout) as client:
            for section in sections:
                concepts = self._concept_candidates(section)
                summaries.append(self._request_or_fallback(client, "summary", section, metadata, concepts))
                flashcards.extend(self._request_or_fallback(client, "flashcards", section, metadata, concepts))
                quizzes.extend(self._request_or_fallback(client, "quiz", section, metadata, concepts))
                for item in self._request_or_fallback(client, "glossary", section, metadata, concepts):
                    term = str(item.get("term") or "").strip().lower()
                    if term and term not in glossary_by_term:
                        glossary_by_term[term] = item
                objectives.extend(self._request_or_fallback(client, "learning-objectives", section, metadata, concepts))

        return {
            "summaries": self._to_existing_summaries(summaries),
            "flashcards": self._to_existing_flashcards(flashcards),
            "quizzes": self._to_existing_quizzes(quizzes),
            "glossary": list(glossary_by_term.values())[:80],
            "learning_objectives": objectives[:80],
            "reports": {
                "gemma_generation": {
                    "section_count": len(sections),
                    "summary_count": len(summaries),
                    "flashcard_count": len(flashcards),
                    "quiz_count": len(quizzes),
                    "glossary_count": len(glossary_by_term),
                    "learning_objective_count": len(objectives),
                    "inference_url": self.inference_url,
                }
            },
        }

    def _fallback_all(self, sections: list[StructuredSection]) -> dict[str, Any]:
        summaries = []
        flashcards = []
        quizzes = []
        glossary_by_term = {}
        objectives = []
        for section in sections:
            concepts = self._concept_candidates(section)
            summaries.append(self._fallback("summary", section, concepts))
            flashcards.extend(self._fallback("flashcards", section, concepts))
            quizzes.extend(self._fallback("quiz", section, concepts))
            for item in self._fallback("glossary", section, concepts):
                glossary_by_term.setdefault(str(item.get("term") or "").lower(), item)
            objectives.extend(self._fallback("learning-objectives", section, concepts))
        return {
            "summaries": self._to_existing_summaries(summaries),
            "flashcards": self._to_existing_flashcards(flashcards),
            "quizzes": self._to_existing_quizzes(quizzes),
            "glossary": list(glossary_by_term.values())[:80],
            "learning_objectives": objectives[:80],
            "reports": {"gemma_generation": {"section_count": len(sections), "fallback": True, "reason": "httpx_unavailable"}},
        }

    def _request_or_fallback(
        self,
        client: httpx.Client,
        artifact: str,
        section: StructuredSection,
        metadata: dict[str, Any],
        concepts: list[str],
    ) -> Any:
        section_hash = str(section.metadata.get("section_hash") or hashlib.sha256(section.content.encode("utf-8")).hexdigest())
        cache_key = (artifact, section_hash)
        if cache_key in self._cache:
            return self._cache[cache_key]
        payload = {
            "section_id": section.section_id,
            "title": section.title,
            "content": section.content,
            "concepts": concepts,
            "grade": metadata.get("grade"),
            "subject": metadata.get("subject"),
            "chapter": metadata.get("chapter"),
            "language": metadata.get("language"),
        }
        endpoint = f"{self.inference_url}/ai/content/{artifact}"
        try:
            response = client.post(endpoint, json=payload)
            response.raise_for_status()
            data = response.json()
            result = data.get("items") if isinstance(data, dict) and "items" in data else data
        except Exception as exc:
            logger.warning("Gemma artifact generation fallback artifact=%s section=%s error=%s", artifact, section.section_id, exc)
            result = self._fallback(artifact, section, concepts)
        self._cache[cache_key] = result
        return result

    def _fallback(self, artifact: str, section: StructuredSection, concepts: list[str]) -> Any:
        sentences = self._sentences(section.content)
        if artifact == "summary":
            return {
                "title": section.title,
                "summary": " ".join(sentences[:4])[:1200],
                "keyPoints": sentences[:5],
                "importantFacts": sentences[5:10] or sentences[:3],
            }
        if artifact == "flashcards":
            return [{"question": f"What is {term}?", "answer": self._sentence_with(section.content, term), "difficulty": "medium"} for term in concepts[:10]]
        if artifact == "quiz":
            return [
                {
                    "question": f"Which statement best explains {term}?",
                    "options": [self._sentence_with(section.content, term), "A related but incorrect statement", "A page heading", "An unrelated term"],
                    "answer": self._sentence_with(section.content, term),
                    "explanation": f"The source section states: {self._sentence_with(section.content, term)}",
                }
                for term in concepts[:5]
            ]
        if artifact == "glossary":
            return [{"term": term.title(), "definition": self._sentence_with(section.content, term)} for term in concepts[:12]]
        if artifact == "learning-objectives":
            return [{"objective": f"Explain {term}."} for term in concepts[:5]]
        return []

    @staticmethod
    def _to_existing_summaries(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "title": str(item.get("title") or "Section Summary"),
                "text": str(item.get("summary") or ""),
                "key_terms": [str(value) for value in item.get("keyPoints", [])[:12]],
                "important_facts": item.get("importantFacts", []),
            }
            for item in items
            if isinstance(item, dict) and str(item.get("summary") or "").strip()
        ]

    @staticmethod
    def _to_existing_flashcards(items: list[dict[str, Any]]) -> list[dict[str, str]]:
        cards = []
        seen = set()
        for item in items:
            question = str(item.get("question") or "").strip()
            answer = str(item.get("answer") or "").strip()
            if question and answer and question.lower() not in seen:
                cards.append({"front": question, "back": answer, "difficulty": str(item.get("difficulty") or "medium")})
                seen.add(question.lower())
        return cards[:120]

    @staticmethod
    def _to_existing_quizzes(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        quizzes = []
        for item in items:
            options = [str(value) for value in item.get("options", []) if str(value).strip()]
            answer = str(item.get("answer") or "").strip()
            if len(options) >= 4 and answer:
                quizzes.append(
                    {
                        "question": str(item.get("question") or "").strip(),
                        "options": [{"label": chr(ord("A") + idx), "text": text} for idx, text in enumerate(options[:4])],
                        "correct_answer": answer,
                        "answer_label": "A" if options and options[0] == answer else "",
                        "explanation": str(item.get("explanation") or ""),
                        "difficulty": str(item.get("difficulty") or "medium"),
                        "source": "gemma_section_generation",
                    }
                )
        return quizzes[:80]

    @staticmethod
    def _concept_candidates(section: StructuredSection) -> list[str]:
        text = section.content
        candidates = []
        for match in re_find_terms(text):
            lowered = match.lower()
            if lowered not in {item.lower() for item in candidates}:
                candidates.append(match)
            if len(candidates) >= 20:
                break
        return candidates

    @staticmethod
    def _sentences(text: str) -> list[str]:
        import re

        return [part.strip() for part in re.split(r"(?<=[.!?])\s+", str(text or "")) if len(part.strip()) > 20]

    def _sentence_with(self, text: str, term: str) -> str:
        for sentence in self._sentences(text):
            if term.lower() in sentence.lower():
                return sentence[:360]
        sentences = self._sentences(text)
        return sentences[0][:360] if sentences else term


def re_find_terms(text: str) -> list[str]:
    import re

    phrases = re.findall(r"\b[A-Z][A-Za-z]*(?:\s+[A-Za-z][A-Za-z]*){0,3}\b", text)
    glossary_like = re.findall(r"\b([a-z][a-z]+(?:\s+[a-z][a-z]+){0,2})\s+(?:is|are|means|refers to|defined as)\b", text, re.I)
    values = [*phrases, *glossary_like]
    stop = {"The", "This", "That", "For", "When", "Where", "Activity", "Exercise", "Chapter"}
    return [value.strip() for value in values if value.strip() and value.strip() not in stop and len(value.split()) <= 4]
