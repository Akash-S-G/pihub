from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse


router = APIRouter(prefix="/api/v1/pdf", tags=["PDF Reader API"])


def _repository(request: Request):
    return request.app.state.pdf_repository


def _registration_service(request: Request):
    return request.app.state.pdf_registration_service


def _reference_payload(reference: Any) -> dict[str, Any]:
    payload = reference.model_dump() if hasattr(reference, "model_dump") else reference.dict()
    payload["pdf_path"] = f"/api/v1/pdf/file/{reference.book_id}"
    payload["source_pdf_path"] = reference.pdf_path
    return payload


@router.get("/catalog")
def get_pdf_catalog(request: Request) -> dict[str, Any]:
    return _registration_service(request).catalog_payload()


@router.get("/chapter/{chapter_id}")
def get_chapter_pdf(chapter_id: str, request: Request) -> dict[str, Any]:
    reference = _repository(request).get_chapter_pdf(chapter_id)
    if reference is None:
        raise HTTPException(status_code=404, detail="PDF chapter mapping not found")
    return _reference_payload(reference)


@router.get("/chapter/{chapter_id}/metadata")
def get_chapter_metadata(chapter_id: str, request: Request) -> dict[str, Any]:
    reference = _repository(request).get_chapter_pdf(chapter_id)
    if reference is None:
        raise HTTPException(status_code=404, detail="PDF chapter mapping not found")
    return {
        "chapter_id": reference.chapter_id,
        "chapter_title": reference.chapter_title,
        "start_page": reference.start_page,
        "end_page": reference.end_page,
        "grade": reference.grade,
        "subject": reference.subject,
        "language": reference.language,
        "book_id": reference.book_id,
    }


@router.get("/book/{grade}/{subject}")
def get_book_metadata(
    grade: int,
    subject: str,
    request: Request,
    language: str = Query(default="english"),
) -> dict[str, Any]:
    books = _repository(request).get_books(grade=grade, subject=subject, language=language)
    if not books:
        raise HTTPException(status_code=404, detail="PDF book not found")
    chapters = [mapping for book in books for mapping in book.chapter_mappings]
    book = books[0]
    return {
        "book_id": f"pdf_grade_{grade}_{subject}_{language}",
        "title": f"Grade {grade} {subject.replace('_', ' ').title()}",
        "grade": book.grade,
        "subject": book.subject,
        "language": book.language,
        "chapter_count": len(chapters),
        "books": [
            {
                "book_id": item.book_id,
                "title": item.book_title,
                "pdf_path": f"/api/v1/pdf/file/{item.book_id}",
                "source_pdf_path": item.pdf_path,
                "chapter_count": len(item.chapter_mappings),
            }
            for item in books
        ],
    }


@router.get("/resolve")
def resolve_pdf_reference(
    request: Request,
    grade: int = Query(...),
    subject: str = Query(...),
    chapter: str = Query(...),
    language: str = Query(default="english"),
) -> dict[str, Any]:
    reference = _repository(request).resolve_pdf_reference(grade=grade, subject=subject, chapter=chapter, language=language)
    if reference is None:
        raise HTTPException(status_code=404, detail="PDF reference not found")
    return _reference_payload(reference)


@router.get("/file/{book_id}")
def get_pdf_file(book_id: str, request: Request):
    book = next((item for item in _repository(request).list_books() if item.book_id == book_id), None)
    if book is None:
        raise HTTPException(status_code=404, detail="PDF book not found")
    pdf_path = Path(book.pdf_path)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF file missing")
    return FileResponse(path=pdf_path, media_type="application/pdf", filename=book.pdf_file)


@router.post("/scan")
def scan_pdf_library(request: Request) -> dict[str, Any]:
    report = _registration_service(request).scan_library()
    _repository(request).reload()
    return report
