#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from certification import APIClient, TutorCertificationRunner


def main() -> int:
    parser = argparse.ArgumentParser(description="Run tutor certification checks through public APIs.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--output-json", default="backend/certification/reports/tutor_certification_report.json")
    parser.add_argument("--output-md", default="backend/certification/reports/tutor_certification_report.md")
    args = parser.parse_args()

    runner = TutorCertificationRunner(APIClient(args.base_url))
    checks = runner.run()
    report = {
        "base_url": args.base_url,
        "checks": [check.__dict__ for check in checks],
    }
    json_path = Path(args.output_json)
    md_path = Path(args.output_md)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_to_markdown(report), encoding="utf-8")
    print(md_path)
    return 0 if all(item["status"] == "PASS" for item in report["checks"]) else 1


def _to_markdown(report: dict[str, object]) -> str:
    lines = ["# Tutor Certification Report", "", f"Base URL: `{report['base_url']}`", "", "## Checks", ""]
    for item in report["checks"]:
        lines.append(f"- {item['name']}: {item['status']}")
        if item.get("detail"):
            lines.append(f"  - {json.dumps(item['detail'], ensure_ascii=False)[:900]}")
    lines.extend(["", "## Verdict", "", "PASS" if all(item["status"] == "PASS" for item in report["checks"]) else "REQUIRES_ADDITIONAL_WORK", ""])
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
