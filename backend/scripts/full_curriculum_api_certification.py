#!/usr/bin/env python3
from __future__ import annotations

import json
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BASE_URL = "http://localhost"
REPORT_PATH = Path("FULL_CURRICULUM_API_CERTIFICATION_REPORT.md")
JSON_PATH = Path("full_curriculum_api_certification.json")
TIMEOUT_SECONDS = 45


@dataclass
class HttpResult:
    method: str
    url: str
    status: int
    duration_ms: float
    headers: dict[str, str]
    body: bytes
    error: str | None = None

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300 and self.error is None

    def text(self, limit: int = 2000) -> str:
        return self.body[:limit].decode("utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))


def request(path: str, *, method: str = "GET", payload: Any | None = None) -> HttpResult:
    url = path if path.startswith("http") else f"{BASE_URL}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    started = time.perf_counter()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            body = response.read()
            status = response.status
            response_headers = {key.lower(): value for key, value in response.headers.items()}
            error = None
    except urllib.error.HTTPError as exc:
        body = exc.read()
        status = exc.code
        response_headers = {key.lower(): value for key, value in exc.headers.items()}
        error = f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001 - certification needs exact transport failures
        body = b""
        status = 0
        response_headers = {}
        error = str(exc)
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    return HttpResult(method=method, url=url, status=status, duration_ms=duration_ms, headers=response_headers, body=body, error=error)


def query(path: str, params: dict[str, Any]) -> str:
    return f"{path}?{urllib.parse.urlencode(params)}"


def as_list(payload: Any, keys: tuple[str, ...]) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def field_text(item: Any, names: tuple[str, ...]) -> str:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return ""
    for name in names:
        value = item.get(name)
        if value is not None:
            return str(value)
    return ""


def quality_score_summary(items: list[Any]) -> tuple[float, list[str]]:
    failures: list[str] = []
    if not items:
        return 0.0, ["empty response"]

    good = 0
    seen: set[str] = set()
    for index, item in enumerate(items[:10]):
        text = field_text(item, ("summary", "text", "content", "description", "answer", "back"))
        normalized = " ".join(text.lower().split())
        if len(normalized) >= 80 and "placeholder" not in normalized and "todo" not in normalized:
            good += 1
        else:
            failures.append(f"item {index} weak summary length={len(text)} preview={text[:80]!r}")
        if normalized and normalized in seen:
            failures.append(f"item {index} duplicate summary preview={text[:80]!r}")
        seen.add(normalized)
    return round(good / max(1, min(10, len(items))) * 100, 2), failures[:6]


def quality_score_flashcards(items: list[Any]) -> tuple[float, list[str]]:
    failures: list[str] = []
    if not items:
        return 0.0, ["empty response"]
    good = 0
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(items[:10]):
        front = field_text(item, ("front", "question", "term", "prompt"))
        back = field_text(item, ("back", "answer", "definition", "explanation"))
        key = (" ".join(front.lower().split()), " ".join(back.lower().split()))
        valid = len(front.strip()) >= 4 and len(back.strip()) >= 20 and key not in seen
        if valid:
            good += 1
        else:
            failures.append(f"item {index} weak/duplicate front={front[:70]!r} back_len={len(back)}")
        seen.add(key)
    return round(good / max(1, min(10, len(items))) * 100, 2), failures[:6]


def quality_score_quizzes(items: list[Any]) -> tuple[float, list[str]]:
    failures: list[str] = []
    if not items:
        return 0.0, ["empty response"]
    good = 0
    for index, item in enumerate(items[:10]):
        question = field_text(item, ("question", "prompt"))
        answer = field_text(item, ("answer", "correct_answer", "correctAnswer"))
        explanation = field_text(item, ("explanation", "rationale"))
        options = []
        if isinstance(item, dict):
            raw_options = item.get("options") or item.get("choices") or []
            if isinstance(raw_options, list):
                options = [str(option) for option in raw_options]
        unique_options = {" ".join(option.lower().split()) for option in options if option.strip()}
        valid = len(question.strip()) >= 12 and len(answer.strip()) >= 1 and len(options) >= 2 and len(unique_options) == len(options)
        if valid:
            good += 1
        else:
            failures.append(
                f"item {index} invalid q_len={len(question)} options={len(options)} "
                f"answer_len={len(answer)} explanation_len={len(explanation)}"
            )
    return round(good / max(1, min(10, len(items))) * 100, 2), failures[:6]


def select_samples(packs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    desired_grades = [1, 3, 5, 6, 8, 10]
    samples: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    for grade in desired_grades:
        grade_packs = [pack for pack in packs if pack.get("grade") == grade]
        for subject in sorted({str(pack.get("subject")) for pack in grade_packs}):
            key = (grade, subject)
            if key in seen:
                continue
            candidate = next((pack for pack in grade_packs if str(pack.get("subject")) == subject), None)
            if candidate:
                samples.append(candidate)
                seen.add(key)
    return samples


def build_report() -> dict[str, Any]:
    raw_results: list[HttpResult] = []

    def tracked(path: str, *, method: str = "GET", payload: Any | None = None) -> HttpResult:
        result = request(path, method=method, payload=payload)
        raw_results.append(result)
        return result

    health = tracked("/health")
    sync = tracked("/packs/sync")
    catalog = tracked("/packs/catalog")
    pdf_catalog = tracked("/api/v1/pdf/catalog")

    health_payload = health.json() if health.ok else {}
    sync_payload = sync.json() if sync.ok else {}
    catalog_payload = catalog.json() if catalog.ok else {}
    pdf_catalog_payload = pdf_catalog.json() if pdf_catalog.ok else {}
    packs = as_list(sync_payload.get("packs", []) if isinstance(sync_payload, dict) else [], ("packs",))

    grade_subject_counter: dict[int, Counter[str]] = defaultdict(Counter)
    grade_chapters: dict[int, set[tuple[str, str]]] = defaultdict(set)
    duplicate_counter: Counter[tuple[int, str, str]] = Counter()
    required_sync_fields = {"pack_id", "version", "checksum", "size_bytes", "manifest_url", "download_url", "artifact_counts"}
    sync_field_failures: list[dict[str, Any]] = []
    missing_content_packs: list[str] = []
    for pack in packs:
        grade = int(pack.get("grade") or 0)
        subject = str(pack.get("subject") or "")
        chapter = str(pack.get("chapter") or "")
        if grade:
            grade_subject_counter[grade][subject] += 1
            grade_chapters[grade].add((subject, chapter))
            duplicate_counter[(grade, subject, chapter)] += 1
        missing = sorted(field for field in required_sync_fields if field not in pack or pack.get(field) in (None, ""))
        if missing:
            sync_field_failures.append({"pack_id": pack.get("pack_id"), "missing": missing})
        counts = pack.get("artifact_counts") or {}
        if isinstance(counts, dict) and int(counts.get("content") or 0) == 0:
            missing_content_packs.append(str(pack.get("pack_id")))

    samples = select_samples(packs)

    manifest_download_rows = []
    for sample in samples:
        manifest_url = sample.get("manifest_url")
        download_url = sample.get("download_url")
        manifest = tracked(str(manifest_url)) if manifest_url else HttpResult("GET", "", 0, 0, {}, b"", "missing manifest_url")
        download = tracked(str(download_url)) if download_url else HttpResult("GET", "", 0, 0, {}, b"", "missing download_url")
        manifest_payload = manifest.json() if manifest.ok else {}
        manifest_download_rows.append(
            {
                "pack_id": sample.get("pack_id"),
                "manifest_http": manifest.status,
                "manifest_pack_id_match": manifest_payload.get("pack_id") == sample.get("pack_id") if isinstance(manifest_payload, dict) else False,
                "download_http": download.status,
                "download_content_type": download.headers.get("content-type", ""),
                "download_content_length": int(download.headers.get("content-length") or len(download.body) or 0),
            }
        )

    pdf_entries = as_list(pdf_catalog_payload, ("entries",))
    pdf_samples = []
    used_pdf_keys: set[tuple[int, str]] = set()
    for entry in pdf_entries:
        grade = int(entry.get("grade") or 0)
        subject = str(entry.get("subject") or "")
        if grade in {1, 3, 5, 6, 8, 10} and (grade, subject) not in used_pdf_keys:
            pdf_samples.append(entry)
            used_pdf_keys.add((grade, subject))
    pdf_rows = []
    for entry in pdf_samples:
        resolve_path = query(
            "/api/v1/pdf/resolve",
            {
                "grade": entry.get("grade"),
                "subject": entry.get("subject"),
                "chapter": entry.get("chapter"),
                "language": entry.get("language", "english"),
            },
        )
        resolved = tracked(resolve_path)
        resolved_payload = resolved.json() if resolved.ok else {}
        file_ok = False
        file_status = None
        file_length = 0
        if isinstance(resolved_payload, dict) and resolved_payload.get("pdf_path"):
            file_result = tracked(str(resolved_payload["pdf_path"]))
            file_ok = file_result.ok and len(file_result.body) > 0
            file_status = file_result.status
            file_length = int(file_result.headers.get("content-length") or len(file_result.body) or 0)
        pdf_rows.append(
            {
                "grade": entry.get("grade"),
                "subject": entry.get("subject"),
                "chapter": entry.get("chapter"),
                "resolve_http": resolved.status,
                "required_metadata": all(
                    key in resolved_payload and resolved_payload.get(key) not in (None, "")
                    for key in ("pdf_path", "start_page", "end_page", "chapter_title")
                )
                if isinstance(resolved_payload, dict)
                else False,
                "file_http": file_status,
                "file_bytes": file_length,
                "file_ok": file_ok,
                "failure_preview": resolved.text(300) if not resolved.ok else "",
            }
        )

    asset_results: dict[str, list[dict[str, Any]]] = {"summaries": [], "flashcards": [], "quizzes": []}
    quality_functions = {
        "summaries": quality_score_summary,
        "flashcards": quality_score_flashcards,
        "quizzes": quality_score_quizzes,
    }
    for sample in samples:
        params = {
            "grade": sample.get("grade"),
            "subject": sample.get("subject"),
            "chapter": sample.get("chapter"),
        }
        for family in asset_results:
            result = tracked(query(f"/{family}", params))
            payload = result.json() if result.ok else []
            items = as_list(payload, (family, "items", "results"))
            score, failures = quality_functions[family](items)
            asset_results[family].append(
                {
                    "grade": sample.get("grade"),
                    "subject": sample.get("subject"),
                    "chapter": sample.get("chapter"),
                    "http": result.status,
                    "item_count": len(items),
                    "score": score,
                    "failures": failures,
                    "preview": result.text(300) if not result.ok else "",
                }
            )

    tutor_questions = [
        {"question": "What is photosynthesis?", "grade": 8, "subject": "science", "chapter": "curiosity"},
        {"question": "Explain proportional reasoning with an example.", "grade": 8, "subject": "maths", "chapter": "proportional reasoning"},
        {"question": "What is democracy?", "grade": 9, "subject": "social_science", "chapter": "what is democracy why democracy"},
        {"question": "Explain force.", "grade": 9, "subject": "science", "chapter": "force and laws of motion"},
        {"question": "What is an ecosystem?", "grade": 10, "subject": "science", "chapter": "our environment"},
        {"question": "What is a fraction?", "grade": 6, "subject": "maths", "chapter": "fractions"},
    ]
    tutor_rows = []
    for payload in tutor_questions:
        result = tracked("/ai/tutor", method="POST", payload={**payload, "stream": False})
        response = result.json() if result.ok else {}
        answer = field_text(response, ("answer", "text", "response", "content"))
        if not answer and isinstance(response, dict):
            answer = json.dumps(response)[:1000]
        terms = [word.strip("?.!,").lower() for word in payload["question"].split() if len(word.strip("?.!,")) > 3]
        overlap = sum(1 for term in terms if term in answer.lower())
        tutor_rows.append(
            {
                "question": payload["question"],
                "http": result.status,
                "answer_length": len(answer),
                "term_overlap": overlap,
                "success": result.ok and len(answer) >= 80,
                "preview": answer[:160] if result.ok else result.text(300),
            }
        )

    reliability: dict[str, dict[str, Any]] = {}
    for family, predicate in {
        "platform": lambda result: "/health" in result.url or "/packs/catalog" in result.url or "/packs/sync" in result.url,
        "packs": lambda result: "/packs/" in result.url and "/api/v1/pdf" not in result.url,
        "pdf": lambda result: "/api/v1/pdf" in result.url,
        "summaries": lambda result: "/summaries" in result.url,
        "flashcards": lambda result: "/flashcards" in result.url,
        "quizzes": lambda result: "/quizzes" in result.url,
        "tutor": lambda result: "/ai/tutor" in result.url,
    }.items():
        family_results = [result for result in raw_results if predicate(result)]
        if not family_results:
            continue
        reliability[family] = {
            "requests": len(family_results),
            "success_rate": round(sum(1 for result in family_results if result.ok) / len(family_results) * 100, 2),
            "average_latency_ms": round(statistics.mean(result.duration_ms for result in family_results), 2),
            "failure_count": sum(1 for result in family_results if not result.ok),
        }

    summary_scores = [item["score"] for item in asset_results["summaries"]]
    flashcard_scores = [item["score"] for item in asset_results["flashcards"]]
    quiz_scores = [item["score"] for item in asset_results["quizzes"]]
    pdf_success_rate = round(sum(1 for row in pdf_rows if row["resolve_http"] == 200 and row["required_metadata"] and row["file_ok"]) / max(1, len(pdf_rows)) * 100, 2)
    tutor_success_rate = round(sum(1 for row in tutor_rows if row["success"]) / max(1, len(tutor_rows)) * 100, 2)
    duplicate_entries = [(grade, subject, chapter, count) for (grade, subject, chapter), count in duplicate_counter.items() if count > 1]

    blocking_reasons = []
    if health_payload.get("status") != "healthy":
        blocking_reasons.append(f"health status is {health_payload.get('status')}")
    if pdf_success_rate < 100:
        blocking_reasons.append(f"PDF resolve success rate is {pdf_success_rate}%")
    if duplicate_entries:
        blocking_reasons.append(f"duplicate curriculum entries remain: {len(duplicate_entries)}")
    if sync_field_failures:
        blocking_reasons.append(f"sync contract field failures: {len(sync_field_failures)}")
    if missing_content_packs:
        blocking_reasons.append(f"packs with zero content artifacts: {len(missing_content_packs)}")
    if statistics.mean(summary_scores or [0]) < 90:
        blocking_reasons.append("summary quality below 90")
    if statistics.mean(flashcard_scores or [0]) < 90:
        blocking_reasons.append("flashcard quality below 90")
    if statistics.mean(quiz_scores or [0]) < 90:
        blocking_reasons.append("quiz quality below 90")
    if tutor_success_rate < 90:
        blocking_reasons.append(f"tutor success rate is {tutor_success_rate}%")

    return {
        "base_url": BASE_URL,
        "final_verdict": "APPROVED_FOR_PRODUCTION" if not blocking_reasons else "REQUIRES_ADDITIONAL_WORK",
        "blocking_reasons": blocking_reasons,
        "health": {
            "http": health.status,
            "status": health_payload.get("status"),
            "pack_count": health_payload.get("pack_count"),
            "chunk_count": health_payload.get("chunk_count"),
        },
        "sync": {
            "http": sync.status,
            "pack_count": len(packs),
            "required_field_failures": sync_field_failures[:20],
            "missing_content_packs": missing_content_packs[:50],
            "sample": packs[0] if packs else None,
        },
        "coverage": {
            "grades": {
                str(grade): {
                    "subjects": sorted(counter.keys()),
                    "pack_count": sum(counter.values()),
                    "chapter_count": len(grade_chapters[grade]),
                }
                for grade, counter in sorted(grade_subject_counter.items())
            },
            "duplicate_entries": duplicate_entries[:50],
            "duplicate_count": len(duplicate_entries),
        },
        "catalog": catalog_payload,
        "manifest_download_rows": manifest_download_rows,
        "pdf": {
            "catalog_http": pdf_catalog.status,
            "catalog_total_entries": pdf_catalog_payload.get("total_entries") if isinstance(pdf_catalog_payload, dict) else None,
            "samples_checked": len(pdf_rows),
            "success_rate": pdf_success_rate,
            "rows": pdf_rows,
        },
        "assets": {
            "summaries": {
                "quality_score": round(statistics.mean(summary_scores or [0]), 2),
                "rows": asset_results["summaries"],
            },
            "flashcards": {
                "quality_score": round(statistics.mean(flashcard_scores or [0]), 2),
                "rows": asset_results["flashcards"],
            },
            "quizzes": {
                "quality_score": round(statistics.mean(quiz_scores or [0]), 2),
                "rows": asset_results["quizzes"],
            },
        },
        "tutor": {
            "success_rate": tutor_success_rate,
            "rows": tutor_rows,
        },
        "reliability": reliability,
        "raw_failure_samples": [
            {
                "method": result.method,
                "url": result.url,
                "status": result.status,
                "error": result.error,
                "preview": result.text(300),
            }
            for result in raw_results
            if not result.ok
        ][:30],
    }


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(item) for item in row) + " |")
    return "\n".join(lines)


def write_markdown(report: dict[str, Any]) -> None:
    lines: list[str] = [
        "# Full Curriculum API Certification Report",
        "",
        "Generated using only public HTTP requests to the exposed Docker backend at `http://localhost`. No pack folders, databases, repository internals, or artifact files were inspected.",
        "",
        f"Final verdict: **{report['final_verdict']}**",
        "",
    ]
    if report["blocking_reasons"]:
        lines.append("Blocking reasons:")
        lines.extend(f"- {reason}" for reason in report["blocking_reasons"])
        lines.append("")

    health = report["health"]
    sync = report["sync"]
    lines.extend(
        [
            "## Environment",
            f"- Base URL: `{report['base_url']}`",
            f"- Health HTTP: `{health['http']}`",
            f"- Health status: `{health['status']}`",
            f"- Health pack_count: `{health['pack_count']}`",
            f"- Health chunk_count: `{health['chunk_count']}`",
            f"- `/packs/sync` HTTP: `{sync['http']}`",
            f"- `/packs/sync` pack count: `{sync['pack_count']}`",
            "",
            "## Grade Coverage",
        ]
    )
    coverage_rows = []
    for grade, info in report["coverage"]["grades"].items():
        coverage_rows.append([grade, ", ".join(info["subjects"]), info["chapter_count"], info["pack_count"]])
    lines.append(md_table(["Grade", "Subjects", "Chapter Count", "Pack Count"], coverage_rows))
    lines.extend(
        [
            "",
            "## Curriculum Duplicates",
            f"- Duplicate grade/subject/chapter tuples: `{report['coverage']['duplicate_count']}`",
        ]
    )
    if report["coverage"]["duplicate_entries"]:
        lines.append("```json")
        lines.append(json.dumps(report["coverage"]["duplicate_entries"][:20], indent=2, ensure_ascii=False))
        lines.append("```")
    lines.extend(
        [
            "",
            "## Sync Contract Validation",
            f"- Required-field failures: `{len(sync['required_field_failures'])}`",
            f"- Packs with `artifact_counts.content == 0`: `{len(sync['missing_content_packs'])}`",
            "- Sample sync entry:",
            "```json",
            json.dumps(sync["sample"], indent=2, ensure_ascii=False)[:3000],
            "```",
            "",
            "## Manifest And Download Validation",
        ]
    )
    lines.append(
        md_table(
            ["Pack", "Manifest HTTP", "Pack ID Match", "Download HTTP", "Content-Type", "Content-Length"],
            [
                [
                    f"`{row['pack_id']}`",
                    row["manifest_http"],
                    row["manifest_pack_id_match"],
                    row["download_http"],
                    f"`{row['download_content_type']}`",
                    row["download_content_length"],
                ]
                for row in report["manifest_download_rows"]
            ],
        )
    )
    lines.extend(
        [
            "",
            "## Reader / PDF API Validation",
            f"- PDF catalog entries: `{report['pdf']['catalog_total_entries']}`",
            f"- PDF sampled chapters: `{report['pdf']['samples_checked']}`",
            f"- PDF resolve success rate: `{report['pdf']['success_rate']}%`",
        ]
    )
    lines.append(
        md_table(
            ["Grade", "Subject", "Chapter", "Resolve HTTP", "Required Metadata", "PDF File HTTP", "PDF Bytes"],
            [
                [
                    row["grade"],
                    row["subject"],
                    row["chapter"],
                    row["resolve_http"],
                    row["required_metadata"],
                    row["file_http"],
                    row["file_bytes"],
                ]
                for row in report["pdf"]["rows"]
            ],
        )
    )
    for family in ("summaries", "flashcards", "quizzes"):
        section = report["assets"][family]
        title = family.capitalize()
        lines.extend(["", f"## {title} Validation", f"- {title} Quality Score: `{section['quality_score']}`"])
        failing = [row for row in section["rows"] if row["score"] < 80 or row["http"] != 200]
        lines.append(f"- Failing samples: `{len(failing)}`")
        for row in failing[:8]:
            lines.append(
                f"- `GET /{family}?grade={row['grade']}&subject={row['subject']}&chapter={row['chapter']}` "
                f"-> HTTP {row['http']}, score={row['score']}, item_count={row['item_count']}, failures={json.dumps(row['failures'][:3], ensure_ascii=False)}"
            )
    lines.extend(
        [
            "",
            "## Tutor Validation",
            f"- Tutor Success Rate: `{report['tutor']['success_rate']}%`",
        ]
    )
    lines.append(
        md_table(
            ["Question", "HTTP", "Answer Length", "Term Overlap", "Success", "Preview"],
            [
                [
                    row["question"],
                    row["http"],
                    row["answer_length"],
                    row["term_overlap"],
                    row["success"],
                    row["preview"].replace("|", "\\|"),
                ]
                for row in report["tutor"]["rows"]
            ],
        )
    )
    lines.extend(["", "## API Reliability"])
    lines.append(
        md_table(
            ["Family", "Requests", "Success Rate", "Avg Latency ms", "Failures"],
            [
                [family, info["requests"], f"{info['success_rate']}%", info["average_latency_ms"], info["failure_count"]]
                for family, info in sorted(report["reliability"].items())
            ],
        )
    )
    if report["raw_failure_samples"]:
        lines.extend(["", "## Broken Endpoints And Sample Failures"])
        for failure in report["raw_failure_samples"]:
            lines.append(
                f"- {failure['method']} {failure['url']} -> status={failure['status']} error={failure['error']} preview={failure['preview']!r}"
            )
    lines.extend(["", "## Certification Conclusion", f"**{report['final_verdict']}**", ""])
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    report = build_report()
    JSON_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(report)
    print(json.dumps({"verdict": report["final_verdict"], "blocking_reasons": report["blocking_reasons"]}, indent=2))


if __name__ == "__main__":
    main()
