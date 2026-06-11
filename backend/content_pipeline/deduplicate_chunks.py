from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher
from typing import Any

from .chunk_cleaner import normalize_text


def exact_key(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def near_duplicate_key(text: str, shingle_size: int = 5, selected_count: int = 18) -> str:
    words = re.findall(r"[a-z0-9]+", normalize_text(text))
    if len(words) < shingle_size * 2:
        return ""
    shingles = {" ".join(words[index:index + shingle_size]) for index in range(len(words) - shingle_size + 1)}
    selected = sorted(shingles)[:selected_count]
    return hashlib.sha1("|".join(selected).encode("utf-8")).hexdigest()


def similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, normalize_text(left), normalize_text(right)).ratio()


def deduplicate_chunks(chunks: list[dict[str, Any]], near_threshold: float = 0.92) -> tuple[list[dict[str, Any]], dict[str, int]]:
    exact_seen: set[str] = set()
    near_seen: dict[str, str] = {}
    output: list[dict[str, Any]] = []
    metrics = {
        "chunks_input": len(chunks),
        "chunks_output": 0,
        "exact_duplicates_removed": 0,
        "near_duplicates_removed": 0,
    }
    for chunk in chunks:
        text = str(chunk.get("text") or "")
        key = exact_key(text)
        if key in exact_seen:
            metrics["exact_duplicates_removed"] += 1
            continue
        exact_seen.add(key)

        near_key = near_duplicate_key(text)
        if near_key and near_key in near_seen and similarity(text, near_seen[near_key]) >= near_threshold:
            metrics["near_duplicates_removed"] += 1
            continue
        if near_key:
            near_seen[near_key] = text
        output.append(chunk)

    metrics["chunks_output"] = len(output)
    return output, metrics

