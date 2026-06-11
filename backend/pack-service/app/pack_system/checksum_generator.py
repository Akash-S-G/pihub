from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class ChecksumGenerator:
    @staticmethod
    def canonical_json(data: Any) -> str:
        return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)

    @classmethod
    def checksum_dict(cls, data: Any) -> str:
        payload = cls.canonical_json(data).encode("utf-8")
        return f"sha256:{hashlib.sha256(payload).hexdigest()}"

    @staticmethod
    def checksum_bytes(data: bytes) -> str:
        return f"sha256:{hashlib.sha256(data).hexdigest()}"

    @classmethod
    def checksum_file(cls, path: Path) -> str:
        return cls.checksum_bytes(path.read_bytes())
