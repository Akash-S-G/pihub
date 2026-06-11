from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException
from fastapi.responses import FileResponse


class PackDownloadService:
    def download(self, record: dict[str, Any]) -> FileResponse:
        archive_path = record.get("archive_path")
        if not archive_path:
            raise HTTPException(status_code=404, detail="Pack archive not found")

        path = Path(archive_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Pack archive not found")

        return FileResponse(path=path, filename=path.name, media_type="application/gzip")
