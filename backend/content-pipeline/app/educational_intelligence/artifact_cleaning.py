from __future__ import annotations

import re
from collections import Counter
from typing import Any

from shared.text_normalization import normalize_language_code

OCR_MARKERS = (
    "/square6",
    "\u25a1",
    "reprint 2025-26",
    "reprint 205-6",
    "chapter notes",
)

KANNADA_FALLBACKS = {
    "question": "ಪ್ರಶ್ನೆ",
    "related": "ಸಂಬಂಧಿತ",
    "unrelated": "ಸಂಬಂಧಿಸದ",
    "generic_phrase": "ಸಾಮಾನ್ಯ ಪಠ್ಯಪುಸ್ತಕ ಪದಬಳಕೆ",
    "incomplete_idea": "ಅಧ್ಯಾಯದ ಸಂಬಂಧಿತ ಆದರೆ ಅಪೂರ್ಣ ಕಲ್ಪನೆ",
    "different_concept": "ಸಂಪೂರ್ಣವಾಗಿ ಬೇರೆ ಕಲ್ಪನೆ",
    "non_matching": "ಹೊಂದಿಕೆಯಾಗದ ಹೇಳಿಕೆ",
}

GENERIC_PHRASES = (
    "only related to",
    "important idea studied",
    "important idea from the chapter notes",
    "review the chapter notes",
    "the following question",
    "what is ",
    "how do you use ",
    "concept:",
    "problem:",
    "step 1:",
    "step 2:",
)

GENERIC_TERMS = {
    "a", "an", "and", "are", "both", "correct", "example", "idea", "image", "object", "paper",
    "reason", "size", "surface", "beam", "glass", "light", "mirror", "plane", "concave", "convex",
}


def normalize_text(text: str) -> str:
    value = str(text or "").replace("\u00a0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def clean_text(text: str) -> str:
    value = normalize_text(text)
    value = value.replace("•", ". ")
    value = re.sub(r"\s*[/\\]square6\s*", " ", value, flags=re.I)
    value = re.sub(r"\bReprint\s+\d{3,4}-\d{1,2}\b", "", value, flags=re.I)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" -:;")


def sentence_split(text: str) -> list[str]:
    parts = [segment.strip() for segment in re.split(r"(?<=[.!?।])\s+", normalize_text(text)) if segment.strip()]
    return parts


def tokenize(text: str) -> list[str]:
    return re.findall(r"[\w\u0900-\u097F\u0C80-\u0CFF][\w\u0900-\u097F\u0C80-\u0CFF'/-]{1,}", normalize_text(text))


def is_noisy_text(text: str) -> bool:
    value = normalize_text(text).lower()
    if not value:
        return True
    if any(marker in value for marker in OCR_MARKERS):
        return True
    if any(phrase in value for phrase in GENERIC_PHRASES):
        return True
    if len(tokenize(value)) <= 1 and len(value) < 5:
        return True
    return False


def is_meaningful_term(term: str) -> bool:
    value = clean_text(term)
    if is_noisy_text(value):
        return False
    lowered = value.lower()
    if lowered in GENERIC_TERMS:
        return False
    if lowered.startswith(("what ", "how ", "why ", "the following", "chapter ", "concept ", "problem ", "step ", "both ")):
        return False
    if " assertion and reason" in lowered or " chapter notes" in lowered:
        return False
    if "/" in lowered and not re.search(r"[a-z]+/[a-z]+", lowered):
        return False
    return True


def dedupe_by_key(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        value = normalize_text(str(item.get(key) or "")).lower()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(item)
    return result


def pick_anchor_sentence(text: str, term: str | None = None) -> str:
    sentences = [sentence for sentence in sentence_split(clean_text(text)) if sentence and not is_noisy_text(sentence)]
    if not sentences:
        return clean_text(text)[:220]
    if term:
        term_l = term.lower()
        for sentence in sentences:
            if term_l in sentence.lower():
                return sentence
    scored: list[tuple[int, int, str]] = []
    for sentence in sentences:
        tokens = tokenize(sentence)
        score = len(tokens)
        if any(token.lower() in {"is", "are", "means", "refers", "shows", "forms", "helps", "requires"} for token in tokens):
            score += 4
        scored.append((score, len(sentence), sentence))
    scored.sort(reverse=True)
    return scored[0][2]


def extract_candidate_terms(text: str) -> list[str]:
    tokens = tokenize(text)
    counts = Counter(token.strip("-/").title() for token in tokens if is_meaningful_term(token))
    return [term for term, _ in counts.most_common(20)]


def build_mcq_options(answer: str, distractor_pool: list[str], limit: int = 4, language: str | None = None) -> list[str]:
    options = [clean_text(answer)]
    language_code = normalize_language_code(language)
    for candidate in distractor_pool:
        candidate_clean = clean_text(candidate)
        if not candidate_clean or candidate_clean == options[0] or candidate_clean in options:
            continue
        options.append(candidate_clean)
        if len(options) >= limit:
            break
    while len(options) < limit:
        fallback = "ಅಧ್ಯಾಯಕ್ಕೆ ಸಂಬಂಧಿಸದ ಕಲ್ಪನೆ" if language_code == "kn" or re.search(r"[\u0C80-\u0CFF]", answer) else "An unrelated idea from a different chapter"
        if fallback not in options:
            options.append(fallback)
        else:
            options.append(fallback + f" {len(options) + 1}")
    return options[:limit]
