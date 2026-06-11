from __future__ import annotations

from typing import Any


class ManifestSafetyValidator:
    FORBIDDEN_KEYS = {
        "code",
        "source_code",
        "python",
        "dart",
        "flutter",
        "runtime",
        "runtime_state",
        "physics_engine",
        "simulation_engine",
        "execution_state",
        "websocket",
    }

    def sanitize(self, manifest: dict[str, Any]) -> dict[str, Any]:
        return self._sanitize_object(manifest)

    def _sanitize_object(self, value: Any) -> Any:
        if isinstance(value, dict):
            sanitized: dict[str, Any] = {}
            for key, item in value.items():
                if str(key).lower() in self.FORBIDDEN_KEYS:
                    continue
                sanitized[key] = self._sanitize_object(item)
            return sanitized
        if isinstance(value, list):
            return [self._sanitize_object(item) for item in value]
        return value
