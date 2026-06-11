from __future__ import annotations

from fastapi import HTTPException


class VoiceServiceError(HTTPException):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(status_code=status_code, detail={"success": False, "error": {"code": code, "message": message}})


def not_configured(component: str) -> VoiceServiceError:
    return VoiceServiceError(501, "VOICE_RUNTIME_NOT_CONFIGURED", f"{component} runtime is not configured")
