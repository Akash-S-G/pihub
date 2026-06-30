#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from certification import APIClient
from certification.benchmark import DemoReadinessBenchmark


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the 100-question demo readiness benchmark.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--output", default="backend/certification/reports/demo_readiness_benchmark.json")
    args = parser.parse_args()

    benchmark = DemoReadinessBenchmark(APIClient(args.base_url))
    result = benchmark.run()

    output = {
        "base_url": args.base_url,
        **result.__dict__,
    }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
