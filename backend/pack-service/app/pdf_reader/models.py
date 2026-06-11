from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PdfChapterMapping(BaseModel):
    chapter_id: str
    chapter_title: str
    start_page: int = Field(default=1, ge=1)
    end_page: int = Field(default=1, ge=1)
    aliases: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PdfBook(BaseModel):
    book_id: str
    grade: int
    subject: str
    book_title: str
    language: str = "english"
    pdf_path: str
    pdf_file: str
    chapter_mappings: list[PdfChapterMapping] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PdfReference(BaseModel):
    grade: int
    subject: str
    language: str = "english"
    chapter_id: str
    chapter_title: str
    pdf_path: str
    pdf_file: str
    book_id: str
    start_page: int
    end_page: int
    metadata: dict[str, Any] = Field(default_factory=dict)
