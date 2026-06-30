from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .client import APIClient, APIError


@dataclass
class CheckResult:
    name: str
    status: str
    detail: dict[str, Any] = field(default_factory=dict)


class TutorCertificationRunner:
    def __init__(self, client: APIClient) -> None:
        self.client = client

    def run(self) -> list[CheckResult]:
        checks = [
            self.check_retrieval(),
            self.check_chapter_knowledge(),
            self.check_session_memory(),
            self.check_experiment_awareness(),
            self.check_multilingual(),
        ]
        return checks

    def check_retrieval(self) -> CheckResult:
        payload = self._debug_payload("What is evaporation?", grade=6, subject="science", chapter="evaporation", topic="evaporation", session_id="cert-retrieval")
        result = self._debug_tutor(payload)
        diagnostics = result.get("retrieval_diagnostics", {})
        retrieved_chunks = result.get("retrieved_chunks", [])
        status = "PASS" if int(diagnostics.get("chunks_retrieved") or 0) > 0 and len(retrieved_chunks) > 0 else "FAIL"
        return CheckResult("Tutor retrieval", status, {"retrieved_chunks": len(retrieved_chunks), "diagnostics": diagnostics})

    def check_chapter_knowledge(self) -> CheckResult:
        payload = self._debug_payload("Explain photosynthesis.", grade=6, subject="science", chapter="photosynthesis", topic="photosynthesis", session_id="cert-chapter-knowledge")
        result = self._debug_tutor(payload)
        final_prompt = str(result.get("final_prompt") or "")
        asset_mentions = "chapter_knowledge" in final_prompt or "CURATED EDUCATIONAL ASSETS" in final_prompt
        status = "PASS" if asset_mentions else "FAIL"
        return CheckResult("Chapter knowledge usage", status, {"final_prompt_contains_chapter_knowledge": asset_mentions})

    def check_session_memory(self) -> CheckResult:
        session_id = "cert-memory"
        first = self._debug_tutor(self._debug_payload("What is photosynthesis?", grade=6, subject="science", chapter="photosynthesis", topic="photosynthesis", session_id=session_id))
        second = self._debug_tutor(self._debug_payload("Explain it simply.", grade=6, subject="science", chapter="photosynthesis", topic="photosynthesis", session_id=session_id))
        third = self._debug_tutor(self._debug_payload("Give an example.", grade=6, subject="science", chapter="photosynthesis", topic="photosynthesis", session_id=session_id))
        second_prompt = str(second.get("final_prompt") or "")
        third_prompt = str(third.get("final_prompt") or "")
        history_used = "RECENT SESSION HISTORY" in second_prompt and "What is photosynthesis?" in second_prompt
        followup_references = "photosynthesis" in str(second.get("answer") or "").lower() or "photosynthesis" in str(third.get("answer") or "").lower()
        status = "PASS" if history_used and followup_references else "FAIL"
        return CheckResult(
            "Session memory",
            status,
            {
                "first_answer": first.get("answer"),
                "second_answer": second.get("answer"),
                "third_answer": third.get("answer"),
                "history_used": history_used,
                "followup_references": followup_references,
                "second_prompt_contains_history": "RECENT SESSION HISTORY" in second_prompt,
                "third_prompt_contains_history": "RECENT SESSION HISTORY" in third_prompt,
            },
        )

    def check_experiment_awareness(self) -> CheckResult:
        base_payload = self._debug_payload("Why is evaporation increasing?", grade=6, subject="science", chapter="evaporation", topic="evaporation", session_id="cert-experiment")
        hot_payload = dict(base_payload)
        hot_payload["sessionState"] = {
            "experiment_state": {
                "experiment_id": "evaporation-demo",
                "variables": {"temperature": 90},
                "observations": ["Water is disappearing faster."],
                "active_step": {"step": "increase temperature"},
            }
        }
        cold_payload = dict(base_payload)
        cold_payload["sessionState"] = {
            "experiment_state": {
                "experiment_id": "evaporation-demo",
                "variables": {"temperature": 10},
                "observations": ["Water is disappearing slowly."],
                "active_step": {"step": "decrease temperature"},
            }
        }
        hot = self._debug_tutor(hot_payload)
        cold = self._debug_tutor(cold_payload)
        hot_prompt = str(hot.get("final_prompt") or "")
        cold_prompt = str(cold.get("final_prompt") or "")
        prompt_diff = hot_prompt != cold_prompt
        answer_diff = str(hot.get("answer") or "").strip() != str(cold.get("answer") or "").strip()
        status = "PASS" if prompt_diff and answer_diff else "FAIL"
        return CheckResult(
            "Experiment awareness",
            status,
            {
                "prompt_diff": prompt_diff,
                "answer_diff": answer_diff,
                "hot_answer": hot.get("answer"),
                "cold_answer": cold.get("answer"),
            },
        )

    def check_multilingual(self) -> CheckResult:
        checks = {}
        overall = True
        for language in ("en", "hi", "kn"):
            payload = self._tutor_payload("Explain photosynthesis.", grade=6, subject="science", chapter="photosynthesis", topic="photosynthesis", session_id=f"cert-lang-{language}", language=language)
            result = self.client.post_json("/ai/tutor", payload)
            evaluation = self.client.post_json(
                "/ai/tutor/evaluate",
                {
                    "question": payload["question"],
                    "answer": result.get("answer", ""),
                    "context": result.get("context", []),
                    "language": language,
                    "grade": payload["grade"],
                },
            )
            passed = bool(result.get("answer")) and bool(evaluation.get("language_correct"))
            checks[language] = {
                "answer": result.get("answer"),
                "evaluation": evaluation,
                "passed": passed,
            }
            overall = overall and passed
        return CheckResult("Multilingual", "PASS" if overall else "FAIL", checks)

    def _debug_tutor(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.client.post_json("/ai/tutor/debug", payload)

    @staticmethod
    def _debug_payload(question: str, *, grade: int, subject: str, chapter: str, topic: str, session_id: str, language: str = "en") -> dict[str, Any]:
        return {
            "question": question,
            "grade": grade,
            "subject": subject,
            "chapter": chapter,
            "topic": topic,
            "language": language,
            "stream": False,
            "sessionState": {"session_id": session_id},
        }

    def _tutor_payload(self, question: str, **kwargs: Any) -> dict[str, Any]:
        payload = self._debug_payload(question, **kwargs)
        payload["stream"] = False
        return payload
