#!/usr/bin/env python3
"""Retry failed builds from a previous `build_report.json` file."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict

from build_utils import generate_pack_via_pack_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("retry_failed_builds")


def main(report_path: Path = Path.cwd() / "build_report.json") -> int:
    if not report_path.exists():
        logger.error("Report not found: %s", report_path)
        return 1

    data: Dict = json.loads(report_path.read_text(encoding="utf-8"))
    retries = {}

    for file_path, info in data.items():
        status = info.get("status")
        if status == "completed":
            continue

        logger.info("Retrying: %s (status=%s)", file_path, status)
        # Attempt to re-generate pack if we have metadata
        pack_meta = info.get("pack") or info.get("last_pack") or {}
        # If pack_meta is present with pack_id, attempt validate/generate
        try:
            # best-effort: request chapter pack generation using basename
            from pathlib import Path as _P

            chapter = _P(file_path).stem
            resp = generate_pack_via_pack_service("pihub-pack-service", pack_type="chapter", chapter=chapter)
            retries[file_path] = {"status": "retried", "resp": resp}
            logger.info("Retry response: %s", resp)
        except Exception as exc:
            logger.error("Retry failed for %s: %s", file_path, exc)
            retries[file_path] = {"status": "failed", "error": str(exc)}

    out = report_path.parent / "retry_report.json"
    out.write_text(json.dumps(retries, indent=2), encoding="utf-8")
    logger.info("Retry report saved: %s", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
