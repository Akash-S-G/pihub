#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from certification import APIClient, ContentCompletenessAuditor


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a curriculum content completeness report through public APIs.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--output-json", default="backend/certification/reports/content_completeness_report.json")
    parser.add_argument("--output-md", default="backend/certification/reports/content_completeness_report.md")
    args = parser.parse_args()

    auditor = ContentCompletenessAuditor(APIClient(args.base_url))
    report = auditor.run()

    json_path = Path(args.output_json)
    md_path = Path(args.output_md)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(ContentCompletenessAuditor.to_markdown(report), encoding="utf-8")
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
