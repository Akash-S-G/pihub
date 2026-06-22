from __future__ import annotations

import hashlib
import json
from typing import Any

from .models import ConversationSession, utc_now


class SessionManager:
    """In-memory conversation session manager.

    The API is intentionally small so the storage backend can be replaced with
    Redis later without changing the tutor orchestration contract.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, ConversationSession] = {}

    def get_or_create(self, request: Any) -> ConversationSession:
        state = self._merged_state(request)
        session_id = str(state.get("session_id") or state.get("sessionId") or self._stable_session_id(request))
        history = self._history(request)
        session = self._sessions.get(session_id)
        if session is None:
            session = ConversationSession(
                session_id=session_id,
                student_id=self._optional_str(state.get("student_id") or state.get("studentId")),
                language=self._optional_str(getattr(request, "language", None)),
                grade=getattr(request, "grade", None),
                subject=self._optional_str(getattr(request, "subject", None)),
                chapter_id=self._optional_str(state.get("chapter_id") or state.get("chapterId") or getattr(request, "chapter", None)),
                experiment_id=self._optional_str(state.get("experiment_id") or state.get("experimentId")),
                chat_history=history,
            )
            self._sessions[session_id] = session
            return session

        session.language = self._optional_str(getattr(request, "language", None)) or session.language
        session.grade = getattr(request, "grade", None) or session.grade
        session.subject = self._optional_str(getattr(request, "subject", None)) or session.subject
        session.chapter_id = self._optional_str(state.get("chapter_id") or state.get("chapterId") or getattr(request, "chapter", None)) or session.chapter_id
        session.experiment_id = self._optional_str(state.get("experiment_id") or state.get("experimentId")) or session.experiment_id
        session.chat_history = history or session.chat_history
        session.updated_at = utc_now()
        return session

    def append_turn(self, session_id: str, question: str, answer: str) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return
        session.chat_history.append({"role": "student", "content": question})
        session.chat_history.append({"role": "tutor", "content": answer})
        session.updated_at = utc_now()

    def get(self, session_id: str) -> ConversationSession | None:
        return self._sessions.get(session_id)

    @staticmethod
    def _merged_state(request: Any) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for attr in ("sessionState", "session_state"):
            value = getattr(request, attr, None)
            if isinstance(value, dict):
                output.update(value)
        return output

    @staticmethod
    def _history(request: Any) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for attr in ("conversationHistory", "conversation_history"):
            value = getattr(request, attr, None)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        output.append(item)
                    else:
                        output.append({"role": "unknown", "content": str(item)})
        return output

    @staticmethod
    def _stable_session_id(request: Any) -> str:
        payload = {
            "student_id": SessionManager._merged_state(request).get("student_id"),
            "grade": getattr(request, "grade", None),
            "subject": getattr(request, "subject", None),
            "chapter": getattr(request, "chapter", None),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:24]

    @staticmethod
    def _optional_str(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
