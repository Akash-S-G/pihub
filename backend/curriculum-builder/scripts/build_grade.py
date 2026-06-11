#!/usr/bin/env python3
"""Wrapper to build a specific grade using build_curriculum orchestrator."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_curriculum import main as build_main  # type: ignore


if __name__ == "__main__":
    # Forward arguments to build_curriculum with --pilot disabled
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--grade", type=int, required=True)
    parser.add_argument("--dry-run", action="store_true", default=False)
    args = parser.parse_args()

    # Build argv for target script
    argv = ["build_curriculum.py", f"--grade", str(args.grade)]
    if args.dry_run:
        argv.append("--dry-run")

    sys.argv = argv
    build_main()
