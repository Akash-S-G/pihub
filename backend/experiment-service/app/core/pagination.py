from __future__ import annotations

from typing import Any, Sequence

from fastapi import Query


DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def page_query(default: int = 1) -> int:
    return Query(default=default, ge=1)


def page_size_query(default: int = DEFAULT_PAGE_SIZE) -> int:
    return Query(default=default, ge=1, le=MAX_PAGE_SIZE)


def paginate(items: Sequence[Any], page: int, page_size: int) -> dict[str, Any]:
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": list(items[start:end]),
        "page": page,
        "page_size": page_size,
        "total": total,
    }
