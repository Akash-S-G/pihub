from __future__ import annotations

import re


SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


class StorageLayout:
    @staticmethod
    def slugify(value: str) -> str:
        slug = SLUG_PATTERN.sub("_", value.lower()).strip("_")
        return slug or "unknown"

    @classmethod
    def pack_directory_name(cls, grade: int | None, subject: str | None, chapter: str | None, pack_id: str) -> str:
        grade_segment = f"grade_{grade}" if grade is not None else "grade_unknown"
        subject_segment = cls.slugify(subject or "unknown")
        chapter_segment = cls.slugify(chapter or "general")
        return f"{grade_segment}/{subject_segment}/{chapter_segment}/{cls.slugify(pack_id)}"
