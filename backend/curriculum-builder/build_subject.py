#!/usr/bin/env python3
"""Convenience wrapper so `python3 build_subject.py --subject ...` works from this directory."""
from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

from build_curriculum import main as build_main  # type: ignore


if __name__ == "__main__":
    if "--force" not in sys.argv:
        sys.argv.append("--force")
    raise SystemExit(build_main())