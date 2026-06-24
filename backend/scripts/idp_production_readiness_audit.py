#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_QUESTIONS = [
    {"question": "What is photosynthesis?", "grade": 6, "subject": "science", "chapter": "photosynthesis"},
    {"question": "Explain the water cycle.", "grade": 6, "subject": "science", "chapter": "water cycle"},
    {"question": "What is motion?", "grade": 6, "subject": "science", "chapter": "motion"},
    {"question": "What is democracy?", "grade": 8, "subject": "social science", "chapter": "democracy"},
    {"question": "What is proportional reasoning?", "grade": 8, "subject": "mathematics", "chapter": "proportional reasoning"},
] * 20


@dataclass
class EndpointResult:
    endpoint: str
    status: str
    status_code: int | None
    latency_ms: float
    detail: Any


def request_json(base_url: str, method: str, path: str, payload: dict[str, Any] | None = None) -> EndpointResult:
    started = time.perf_counter()
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        method=method,
        headers={"content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8", errors="replace")
            latency = (time.perf_counter() - started) * 1000
            return EndpointResult(path, "PASS", response.status, latency, json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        latency = (time.perf_counter() - started) * 1000
        return EndpointResult(path, "FAIL", exc.code, latency, exc.read().decode("utf-8", errors="replace")[:1000])
    except Exception as exc:
        latency = (time.perf_counter() - started) * 1000
        return EndpointResult(path, "FAIL", None, latency, str(exc))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run IDP backend production readiness checks through public APIs.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--output", default="IDP_PRODUCTION_READINESS_AUDIT_REPORT.md")
    args = parser.parse_args()

    checks: list[EndpointResult] = [
        request_json(args.base_url, "GET", "/health"),
        request_json(args.base_url, "GET", "/packs/sync"),
        request_json(args.base_url, "GET", "/packs/coverage"),
        request_json(args.base_url, "GET", "/demo/topics"),
    ]

    tutor_results: list[EndpointResult] = []
    for item in DEFAULT_QUESTIONS:
        payload = dict(item)
        payload["stream"] = False
        tutor_results.append(request_json(args.base_url, "POST", "/ai/tutor", payload))

    latencies = [result.latency_ms for result in tutor_results if result.status == "PASS"]
    success_count = sum(1 for result in tutor_results if result.status == "PASS")
    report = [
        "# IDP Production Readiness Audit",
        "",
        f"Base URL: `{args.base_url}`",
        "",
        "## Endpoint Checks",
        "",
    ]
    for result in checks:
        report.append(f"- `{result.endpoint}`: {result.status} status={result.status_code} latency_ms={result.latency_ms:.2f}")

    report.extend([
        "",
        "## Tutor Benchmark",
        "",
        f"- Questions tested: {len(tutor_results)}",
        f"- Successful responses: {success_count}",
        f"- Success rate: {(success_count / len(tutor_results)) * 100:.2f}%",
        f"- Average latency ms: {statistics.mean(latencies):.2f}" if latencies else "- Average latency ms: n/a",
        f"- P95 latency ms: {_percentile(latencies, 95):.2f}" if latencies else "- P95 latency ms: n/a",
        "",
        "## Failures",
        "",
    ])
    failures = [result for result in checks + tutor_results if result.status != "PASS"]
    if not failures:
        report.append("No failures observed.")
    else:
        for failure in failures[:25]:
            report.append(f"- `{failure.endpoint}` status={failure.status_code} detail={failure.detail}")

    report.extend([
        "",
        "## Verdict",
        "",
        "PASS" if not failures else "REQUIRES_ADDITIONAL_WORK",
        "",
    ])

    Path(args.output).write_text("\n".join(report), encoding="utf-8")
    print(args.output)
    return 0 if not failures else 1


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((percentile / 100) * (len(ordered) - 1)))
    return ordered[index]


if __name__ == "__main__":
    raise SystemExit(main())
