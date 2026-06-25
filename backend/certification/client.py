from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class APIError(RuntimeError):
    status_code: int | None
    message: str
    body: str | None = None


class APIClient:
    def __init__(self, base_url: str, timeout_seconds: int = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = self._url(path, params)
        request = urllib.request.Request(url, method="GET")
        return self._request_json(request)

    def post_json(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        data = json.dumps(payload or {}).encode("utf-8")
        request = urllib.request.Request(
            self._url(path),
            data=data,
            method="POST",
            headers={"content-type": "application/json"},
        )
        return self._request_json(request)

    def _request_json(self, request: urllib.request.Request) -> Any:
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8", errors="replace")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise APIError(exc.code, f"HTTP {exc.code}", body=body) from exc
        except urllib.error.URLError as exc:
            raise APIError(None, str(exc)) from exc

    def _url(self, path: str, params: dict[str, Any] | None = None) -> str:
        url = f"{self.base_url}{path}"
        if not params:
            return url
        encoded = urllib.parse.urlencode({key: value for key, value in params.items() if value is not None}, doseq=True)
        return f"{url}?{encoded}" if encoded else url
