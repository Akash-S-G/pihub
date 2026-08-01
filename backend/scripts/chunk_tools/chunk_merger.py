from __future__ import annotations

from typing import Any


def group_key(chunk: dict[str, Any]) -> tuple[Any, Any, Any, Any]:
    metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
    return (
        metadata.get("grade"),
        metadata.get("subject"),
        metadata.get("chapter"),
        metadata.get("source") or metadata.get("textbook_name"),
    )


def merge_group(chunks: list[dict[str, Any]], target_min: int, target_max: int, hard_max: int) -> tuple[list[dict[str, Any]], int]:
    merged: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_texts: list[str] = []
    chunks_merged = 0

    def flush() -> None:
        nonlocal current, current_texts
        if current is None:
            return
        item = dict(current)
        item["text"] = "\n\n".join(current_texts).strip()
        metadata = dict(item.get("metadata") or {})
        metadata["merged_chunk_count"] = len(current_texts)
        item["metadata"] = metadata
        merged.append(item)
        current = None
        current_texts = []

    for chunk in chunks:
        text = str(chunk.get("text") or "").strip()
        if not text:
            continue
        if current is None:
            current = chunk
            current_texts = [text]
            continue
        candidate = "\n\n".join([*current_texts, text])
        if len(candidate) <= target_max or len("\n\n".join(current_texts)) < target_min:
            if len(candidate) <= hard_max:
                current_texts.append(text)
                chunks_merged += 1
                continue
        flush()
        current = chunk
        current_texts = [text]
    flush()
    return merged, chunks_merged


def merge_adjacent_chunks(
    chunks: list[dict[str, Any]],
    target_min: int = 800,
    target_max: int = 1500,
    hard_max: int = 5000,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    output: list[dict[str, Any]] = []
    current_key: tuple[Any, Any, Any, Any] | None = None
    current_group: list[dict[str, Any]] = []
    merged_count = 0

    def flush_group() -> None:
        nonlocal current_group, merged_count
        if not current_group:
            return
        merged, count = merge_group(current_group, target_min, target_max, hard_max)
        output.extend(merged)
        merged_count += count
        current_group = []

    for chunk in chunks:
        key = group_key(chunk)
        if current_key is not None and key != current_key:
            flush_group()
        current_key = key
        current_group.append(chunk)
    flush_group()
    return output, {
        "chunks_input": len(chunks),
        "chunks_output": len(output),
        "chunks_merged": merged_count,
    }
