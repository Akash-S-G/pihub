from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_TOPIC_ALIASES: dict[str, str] = {
    "sin theta": "sine",
    "sin θ": "sine",
    "sintheta": "sine",
    "cos theta": "cosine",
    "cos θ": "cosine",
    "costheta": "cosine",
    "tan theta": "tangent",
    "tan θ": "tangent",
    "tantheta": "tangent",
    "pi value": "pi",
    "value of pi": "pi",
    "π value": "pi",
}

PLANNER_TRIGGERS = (
    "teach me",
    "learn",
    "start chapter",
    "revision",
    "study plan",
)


@dataclass(frozen=True)
class TopicNormalization:
    original_topic: str | None
    normalized_topic: str | None
    matched_alias: str | None = None


def _clean(value: str) -> str:
    value = value.strip().lower().replace("_", " ").replace("-", " ")
    value = re.sub(r"\s+", " ", value)
    return value


def _load_external_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}
    inline = os.getenv("PIHUB_TOPIC_ALIASES_JSON")
    if inline:
        try:
            decoded = json.loads(inline)
            if isinstance(decoded, dict):
                aliases.update({str(key): str(value) for key, value in decoded.items()})
        except json.JSONDecodeError:
            pass

    alias_path = os.getenv("PIHUB_TOPIC_ALIASES_PATH")
    if alias_path:
        path = Path(alias_path)
        if path.exists():
            try:
                decoded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(decoded, dict):
                    aliases.update({str(key): str(value) for key, value in decoded.items()})
            except (OSError, json.JSONDecodeError):
                pass
    return aliases


def topic_aliases() -> dict[str, str]:
    aliases = dict(DEFAULT_TOPIC_ALIASES)
    aliases.update(_load_external_aliases())
    return {_clean(key): _clean(value) for key, value in aliases.items()}


def normalize_topic(topic: Any = None, query: Any = None) -> TopicNormalization:
    original = str(topic).strip() if topic is not None and str(topic).strip() else None
    query_text = str(query).strip() if query is not None and str(query).strip() else None
    aliases = topic_aliases()

    if original:
        cleaned_topic = _clean(original)
        if cleaned_topic in aliases:
            return TopicNormalization(original, aliases[cleaned_topic], cleaned_topic)
        for alias, canonical in aliases.items():
            if re.search(rf"\b{re.escape(alias)}\b", cleaned_topic):
                return TopicNormalization(original, canonical, alias)
        return TopicNormalization(original, cleaned_topic)

    if query_text:
        cleaned_query = _clean(query_text)
        for alias, canonical in aliases.items():
            if re.search(rf"\b{re.escape(alias)}\b", cleaned_query):
                return TopicNormalization(None, canonical, alias)

    return TopicNormalization(original, original)


def should_use_planner(intent: Any = None, query: Any = None) -> bool:
    intent_text = _clean(str(intent or ""))
    query_text = _clean(str(query or ""))
    if intent_text in {"lesson", "teach", "study_plan", "revision", "chapter_start"}:
        return True
    return any(trigger in query_text for trigger in PLANNER_TRIGGERS)


def normalize_subject(subject: Any = None) -> Any:
    if subject is None:
        return None
    value = str(subject).strip()
    if value.lower() in {"mathematics", "math", "maths"}:
        return "maths"
    return value
