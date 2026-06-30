#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from certification import APIClient, ContentCompletenessAuditor, TutorCertificationRunner
from certification.benchmark import DemoReadinessBenchmark


def main() -> int:
    parser = argparse.ArgumentParser(description="Run backend certification against public APIs.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--output-dir", default="backend/certification/reports")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    client = APIClient(args.base_url)
    tutor_runner = TutorCertificationRunner(client)
    content_auditor = ContentCompletenessAuditor(client)
    benchmark = DemoReadinessBenchmark(client)

    tutor_checks = tutor_runner.run()
    content_report = content_auditor.run()
    benchmark_result = benchmark.run()

    report = {
        "base_url": args.base_url,
        "tutor_checks": [check.__dict__ for check in tutor_checks],
        "content_completeness": content_report,
        "demo_benchmark": benchmark_result.__dict__,
    }
    (output_dir / "backend_certification_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (output_dir / "backend_certification_report.md").write_text(_to_markdown(report), encoding="utf-8")
    print(output_dir / "backend_certification_report.md")
    return 0 if all(check.status == "PASS" for check in tutor_checks) and benchmark_result.retrieval_success_rate > 0 else 1


def _to_markdown(report: dict[str, object]) -> str:
    tutor_checks = report["tutor_checks"]
    content = report["content_completeness"]
    benchmark = report["demo_benchmark"]
    lines = [
        "# Backend Certification Report",
        "",
        f"Base URL: `{report['base_url']}`",
        "",
        "## Tutor Checks",
        "",
    ]
    for item in tutor_checks:
        lines.append(f"- {item['name']}: {item['status']}")
        detail = item.get("detail") or {}
        if detail:
            lines.append(f"  - {json.dumps(detail, ensure_ascii=False)[:900]}")
    lines.extend([
        "",
        "## Content Completeness",
        "",
        f"- Total packs: {content['total_packs']}",
        f"- Complete packs: {content['complete_packs']}",
        f"- Completion percent: {content['completion_percent']:.2f}%",
        "",
        "## Demo Benchmark",
        "",
        f"- Avg latency ms: {benchmark['avg_latency_ms']:.2f}",
        f"- P95 latency ms: {benchmark['p95_latency_ms']:.2f}",
        f"- Retrieval success rate: {benchmark['retrieval_success_rate']:.2f}%",
        f"- Context usage rate: {benchmark['context_usage_rate']:.2f}%",
        f"- Hallucination rate: {benchmark['hallucination_rate']:.2f}%",
        "",
        "## Verdict",
        "",
        "PASS" if all(item["status"] == "PASS" for item in tutor_checks) else "REQUIRES_ADDITIONAL_WORK",
        "",
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
