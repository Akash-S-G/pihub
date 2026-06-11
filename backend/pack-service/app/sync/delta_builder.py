from __future__ import annotations

from typing import Any

from .update_resolver import UpdateResolver


class DeltaBuilder:
    def __init__(self) -> None:
        self.resolver = UpdateResolver()

    def build(self, host_records: list[dict[str, Any]], current_versions: dict[str, str]) -> dict[str, Any]:
        return self.resolver.resolve(host_records, current_versions)
