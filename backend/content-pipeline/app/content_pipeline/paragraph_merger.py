from __future__ import annotations


class ParagraphMerger:
    """Merge tiny neighboring paragraphs to preserve educational context continuity."""

    def __init__(self, min_chars: int = 120) -> None:
        self.min_chars = min_chars

    def merge(self, paragraphs: list[str]) -> list[str]:
        merged: list[str] = []
        buffer = ""

        for paragraph in paragraphs:
            p = paragraph.strip()
            if not p:
                continue
            if not buffer:
                buffer = p
                continue

            if len(buffer) < self.min_chars:
                buffer = f"{buffer}\n\n{p}"
            else:
                merged.append(buffer)
                buffer = p

        if buffer:
            merged.append(buffer)

        return merged
