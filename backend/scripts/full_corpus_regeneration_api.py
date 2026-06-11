#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


TARGET_GRADES = {1, 2, 3, 4, 5, 6, 7, 9, 10}


def request_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout: int = 180) -> tuple[int, Any, float]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8", errors="replace")
            return response.status, json.loads(text) if text else {}, (time.perf_counter() - started) * 1000
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(text) if text else {}
        except json.JSONDecodeError:
            body = {"raw": text[:1000]}
        return exc.code, body, (time.perf_counter() - started) * 1000


def load_state(path: Path) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"rows": []}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def generation_payload(pack: dict[str, Any]) -> dict[str, Any]:
    return {
        "pack_type": "chapter" if pack.get("chapter") else "class",
        "grade": pack.get("grade"),
        "subject": pack.get("subject"),
        "chapter": pack.get("chapter"),
        "language": pack.get("language") or "english",
        "include_media": False,
        "compression": "gzip",
        "quantize_embeddings": False,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = latest_rows(rows)
    grade_stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"targeted": 0, "published": 0, "rejected": 0, "failed": 0})
    subject_stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"targeted": 0, "published": 0, "rejected": 0, "failed": 0})
    durations = []
    for row in rows:
        grade = str(row.get("grade"))
        subject_key = f"{row.get('grade')}:{row.get('subject')}"
        status = row.get("status")
        grade_stats[grade]["targeted"] += 1
        subject_stats[subject_key]["targeted"] += 1
        if status in {"published", "rejected", "failed"}:
            grade_stats[grade][status] += 1
            subject_stats[subject_key][status] += 1
        durations.append(float(row.get("duration_ms") or 0.0))
    return {
        "total_packs_targeted": len(rows),
        "total_regenerated": sum(1 for row in rows if row.get("status") == "published"),
        "total_published": sum(1 for row in rows if row.get("status") == "published"),
        "total_rejected": sum(1 for row in rows if row.get("status") == "rejected"),
        "total_failed": sum(1 for row in rows if row.get("status") == "failed"),
        "grade_statistics": dict(sorted(grade_stats.items(), key=lambda item: int(item[0]))),
        "subject_statistics": dict(sorted(subject_stats.items())),
        "average_duration_ms": round(mean(durations), 2) if durations else 0.0,
    }


def latest_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_pack: dict[str, dict[str, Any]] = {}
    for row in rows:
        pack_id = str(row.get("pack_id") or "")
        if pack_id:
            by_pack[pack_id] = row
    return list(by_pack.values())


def markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    failure_rows = [row for row in latest_rows(report["rows"]) if row.get("status") != "published"]
    lines = [
        "# Full Corpus Regeneration Report",
        "",
        f"Final verdict: {report['verdict']}",
        "",
        "## Scope",
        "",
        "- Targeted Grades: 1, 2, 3, 4, 5, 6, 7, 9, 10",
        "- Grade 8 was excluded because it is the approved baseline.",
        "- Regeneration was executed through the deployed public `/packs/generate` API, which uses the approved pack-service semantic pipeline.",
        "",
        "## Summary",
        "",
        f"- Total packs targeted: {summary['total_packs_targeted']}",
        f"- Total regenerated: {summary['total_regenerated']}",
        f"- Total published: {summary['total_published']}",
        f"- Total rejected: {summary['total_rejected']}",
        f"- Total failed: {summary['total_failed']}",
        f"- Average request duration ms: {summary['average_duration_ms']}",
        "",
        "## Grade-wise Statistics",
        "",
        "| Grade | Targeted | Published | Rejected | Failed |",
        "| ---: | ---: | ---: | ---: | ---: |",
    ]
    for grade, stats in summary["grade_statistics"].items():
        lines.append(f"| {grade} | {stats['targeted']} | {stats['published']} | {stats['rejected']} | {stats['failed']} |")
    lines.extend(["", "## Subject-wise Statistics", "", "| Grade:Subject | Targeted | Published | Rejected | Failed |", "| --- | ---: | ---: | ---: | ---: |"])
    for subject, stats in summary["subject_statistics"].items():
        lines.append(f"| {subject} | {stats['targeted']} | {stats['published']} | {stats['rejected']} | {stats['failed']} |")
    lines.extend(["", "## Failure Analysis", "", "```json", json.dumps(failure_rows, indent=2, ensure_ascii=False, sort_keys=True)[:50000], "```"])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost")
    parser.add_argument("--state", default="full_corpus_regeneration_state.json")
    parser.add_argument("--report", default="FULL_CORPUS_REGENERATION_REPORT.md")
    parser.add_argument("--max-packs", type=int, default=0)
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    state_path = Path(args.state)
    state = load_state(state_path)
    completed = {row.get("pack_id") for row in state.get("rows", []) if row.get("status") == "published"}

    status, sync, _duration = request_json("GET", f"{base_url}/packs/sync", timeout=120)
    if status != 200:
        raise SystemExit(f"/packs/sync failed: HTTP {status} {sync}")
    packs = [
        pack
        for pack in sync.get("packs", [])
        if int(pack.get("grade") or 0) in TARGET_GRADES
    ]
    packs = sorted(packs, key=lambda item: (int(item.get("grade") or 0), str(item.get("subject") or ""), str(item.get("chapter") or ""), str(item.get("pack_id") or "")))
    remaining = [pack for pack in packs if pack.get("pack_id") not in completed]
    if args.max_packs > 0:
        remaining = remaining[: args.max_packs]

    for index, pack in enumerate(remaining, start=1):
        payload = generation_payload(pack)
        print(json.dumps({"event": "FULL_CORPUS_API_REGENERATION_START", "index": index, "remaining": len(remaining), "pack_id": pack.get("pack_id")}, ensure_ascii=False), flush=True)
        status, body, duration_ms = request_json("POST", f"{base_url}/packs/generate", payload=payload, timeout=300)
        row = {
            "pack_id": pack.get("pack_id"),
            "grade": pack.get("grade"),
            "subject": pack.get("subject"),
            "chapter": pack.get("chapter"),
            "language": pack.get("language"),
            "request": payload,
            "http_status": status,
            "duration_ms": round(duration_ms, 2),
            "response": body,
            "status": "published" if 200 <= status < 300 else "rejected" if status in {400, 409, 422} else "failed",
        }
        state.setdefault("rows", []).append(row)
        save_state(state_path, state)
        print(json.dumps({"event": "FULL_CORPUS_API_REGENERATION_END", "pack_id": pack.get("pack_id"), "status": row["status"], "http_status": status}, ensure_ascii=False), flush=True)

    rows = state.get("rows", [])
    current_rows = latest_rows(rows)
    report = {
        "verdict": "PASS" if current_rows and all(row.get("status") == "published" for row in current_rows) and len(current_rows) >= len(packs) else "REQUIRES_ADDITIONAL_WORK",
        "target_grades": sorted(TARGET_GRADES),
        "expected_target_count": len(packs),
        "completed_count": len(current_rows),
        "summary": summarize(rows),
        "failure_classes": dict(Counter(row.get("http_status") for row in current_rows if row.get("status") != "published")),
        "rows": rows,
        "latest_rows": current_rows,
    }
    save_state(Path("full_corpus_regeneration_report.json"), report)
    Path(args.report).write_text(markdown(report), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ["verdict", "expected_target_count", "completed_count", "summary"]}, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
