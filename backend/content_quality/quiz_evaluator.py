from __future__ import annotations

from typing import Any

from .common import percent, token_set, word_count


class QuizEvaluator:
    def evaluate_pack(self, pack: dict[str, Any], artifacts: dict[str, Any]) -> list[dict[str, Any]]:
        source_terms = token_set(" ".join(str(item.get("text") or "") for item in artifacts.get("content", [])))
        rows = []
        for quiz in artifacts.get("quizzes", []):
            question = str(quiz.get("question") or "")
            answer = str(quiz.get("correct_answer") or quiz.get("answer") or "")
            explanation = str(quiz.get("explanation") or "")
            options = quiz.get("options") if isinstance(quiz.get("options"), list) else []
            q_terms = token_set(f"{question} {answer} {explanation}")
            rows.append(
                {
                    "pack_id": pack.get("pack_id"),
                    "chapter": pack.get("chapter"),
                    "question": question,
                    "question_correctness": bool(question and answer and word_count(answer) >= 5),
                    "distractor_quality": len(options) >= 4 and any(str(option.get("text", "")) != answer for option in options if isinstance(option, dict)),
                    "explanation_quality": word_count(explanation) >= 8,
                    "curriculum_alignment": bool(q_terms & source_terms),
                    "difficulty_appropriateness": str(quiz.get("difficulty") or "medium") in {"easy", "medium", "hard"},
                }
            )
        return rows

    def evaluate(self, packs: list[dict[str, Any]], artifact_loader, limit: int = 100) -> dict[str, Any]:
        rows = []
        for pack in packs:
            rows.extend(self.evaluate_pack(pack, artifact_loader(pack)))
            if len(rows) >= limit:
                rows = rows[:limit]
                break
        metrics = {}
        fields = ("question_correctness", "distractor_quality", "explanation_quality", "curriculum_alignment", "difficulty_appropriateness")
        for field in fields:
            metrics[field] = percent(sum(1 for row in rows if row[field]), len(rows))
        score = round(sum(metrics.values()) / max(1, len(metrics)), 2)
        return {"quiz_quality": score, "sampled_questions": len(rows), "metrics": metrics, "failures": [row for row in rows if not all(row[field] for field in fields)], "rows": rows}
