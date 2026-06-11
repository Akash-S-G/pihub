from __future__ import annotations

from typing import Any


class QuizValidator:
    def validate(self, quizzes: list[dict[str, Any]]) -> tuple[bool, list[str]]:
        errors: list[str] = []
        if not isinstance(quizzes, list):
            return False, ["quizzes:not-a-list"]

        for index, quiz in enumerate(quizzes):
            question = str(quiz.get("question", "")).strip()
            correct_answer = str(quiz.get("correct_answer", quiz.get("answer", ""))).strip()
            options = quiz.get("options", [])
            if not question:
                errors.append(f"quizzes[{index}]:question-missing")
            if not correct_answer:
                errors.append(f"quizzes[{index}]:answer-missing")
            if options and not isinstance(options, list):
                errors.append(f"quizzes[{index}]:options-not-a-list")

        return not errors, errors
