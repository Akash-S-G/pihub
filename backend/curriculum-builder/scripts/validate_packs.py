#!/usr/bin/env python3
"""Validate packs via pack-service APIs and save a validation report."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Any

from build_utils import list_packs_via_pack_service, validate_pack_via_pack_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("validate_packs")


def main(out_path: Path = Path.cwd() / "pack_validation_report.json") -> int:
    packs = list_packs_via_pack_service("pihub-pack-service")
    items = packs.get("packs") or []
    report: Dict[str, Dict[str, Any]] = {}

    for p in items:
        pack_id = p.get("pack_id")
        logger.info("Validating pack: %s", pack_id)
        try:
            result = validate_pack_via_pack_service("pihub-pack-service", pack_id)
            report[pack_id] = result
        except Exception as exc:
            logger.error("Validation failed for %s: %s", pack_id, exc)
            report[pack_id] = {"error": str(exc)}

    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Validation report written: %s", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
