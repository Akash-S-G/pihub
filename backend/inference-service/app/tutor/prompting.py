from __future__ import annotations

import json
from typing import Any


def append_language_instruction(system_prompt: str, instruction: str) -> str:
    return f"{system_prompt}\n\n[Language Adaptation]\n{instruction}"


def append_experiment_context(user_prompt: str, experiment_context: Any) -> str:
    if not getattr(experiment_context, "has_context", False):
        return user_prompt

    lines = [
        "\nEXPERIMENT CONTEXT:",
        "Use this only when it helps answer the student's current experiment question.",
    ]
    if getattr(experiment_context, "experiment_id", None):
        lines.append(f"Experiment ID: {experiment_context.experiment_id}")
    if getattr(experiment_context, "current_variables", None):
        lines.append("Current variables: " + json.dumps(experiment_context.current_variables, ensure_ascii=False))
    if getattr(experiment_context, "current_observations", None):
        lines.append("Current observations: " + json.dumps(experiment_context.current_observations, ensure_ascii=False))
    if getattr(experiment_context, "active_investigation_step", None):
        lines.append("Active investigation step: " + json.dumps(experiment_context.active_investigation_step, ensure_ascii=False))
    return user_prompt + "\n" + "\n".join(lines)


def append_session_history(user_prompt: str, chat_history: list[dict[str, Any]], limit: int = 8) -> str:
    if not chat_history:
        return user_prompt

    lines = [
        "\nRECENT SESSION HISTORY:",
        "Use this to resolve follow-up questions like 'it', 'that', or 'explain more simply'.",
    ]
    for turn in chat_history[-limit:]:
        role = str(turn.get("role") or "unknown").strip() or "unknown"
        content = str(turn.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"{role}: {content[:800]}")
    if len(lines) == 2:
        return user_prompt
    return user_prompt + "\n" + "\n".join(lines)
