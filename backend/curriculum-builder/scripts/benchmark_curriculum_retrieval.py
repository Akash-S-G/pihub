"""Run the focused curriculum routing benchmark against the local workspace code.

This script compares the newly computed concept-first router output against the
previous saved benchmark baseline and writes a compact comparison report.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = ROOT / "backend"
CONTENT_PIPELINE_ROOT = ROOT / "backend" / "content-pipeline"
REPORT_PATH = ROOT / "backend" / "curriculum-builder" / "curriculum_retrieval_comparison_math.json"
BASELINE_PATH = REPORT_PATH

os.environ["WORK_DIR"] = str(ROOT / ".local_benchmark_shared" / "work")
os.environ["UPLOAD_DIR"] = str(ROOT / ".local_benchmark_shared" / "uploads")
os.environ["CONTENT_DIR"] = str(ROOT / ".local_benchmark_shared" / "content")
os.environ["CACHE_PATH"] = str(ROOT / ".local_benchmark_shared" / "cache")
os.environ["PI_CACHE_DB_PATH"] = str(ROOT / ".local_benchmark_shared" / "cache" / "cache_index.db")
os.environ["PACK_STORAGE_PATH"] = str(ROOT / ".local_benchmark_shared" / "packs")
os.environ["CURRICULUM_GRAPH_PATH"] = str(ROOT / ".local_benchmark_shared" / "work" / "curriculum_graph.json")
os.environ["CURRICULUM_RELATION_GRAPH_PATH"] = str(ROOT / ".local_benchmark_shared" / "work" / "curriculum_relation_graph.json")
os.environ["CURRICULUM_BUILD_DIR"] = str(ROOT / ".local_benchmark_shared" / "curriculum")
os.environ["CURRICULUM_MANIFEST_PATH"] = str(ROOT / ".local_benchmark_shared" / "curriculum" / "curriculum_manifest.json")
os.environ["PACK_REGISTRY_PATH"] = str(ROOT / ".local_benchmark_shared" / "curriculum" / "pack_registry.json")
os.environ["ENRICHMENT_REGISTRY_PATH"] = str(ROOT / ".local_benchmark_shared" / "curriculum" / "enrichment_registry.json")
os.environ["EMBEDDING_MODEL_NAME"] = "sentence-transformers/all-MiniLM-L6-v2"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["QDRANT_COLLECTION"] = "curriculum_chunks"
os.environ["PIPELINE_ENVIRONMENT"] = "local-benchmark"

sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(CONTENT_PIPELINE_ROOT))

from app.main import pipeline  # noqa: E402


def _load_previous_results() -> dict[str, Any]:
    if not BASELINE_PATH.exists():
        return {}

    try:
        payload = json.loads(BASELINE_PATH.read_text())
    except json.JSONDecodeError:
        return {}

    entries = payload if isinstance(payload, list) else payload.get("benchmarks", [])
    previous: dict[str, Any] = {}
    for entry in entries:
        query = entry.get("query")
        if query:
            previous[query] = entry
    return previous


def _extract_previous_router_result(entry: dict[str, Any]) -> Any:
    response = entry.get("response") if isinstance(entry, dict) else None
    if isinstance(response, dict) and "previous" in response:
        return response["previous"]
    return entry.get("previous_router_result") if isinstance(entry, dict) else None


def _route_query(query: str) -> dict[str, Any]:
    candidates, confidence_score, inferred_subject = pipeline.concept_index.route_query_to_chapters(
        query,
        pipeline.curriculum_graph,
    )
    return {
        "selected_chapter": candidates[0] if candidates else None,
        "confidence_score": confidence_score,
        "candidate_chapters": candidates,
        "inferred_subject": inferred_subject,
    }


benchmark_queries = [
    "What is an arithmetic progression?",
    "What is the common difference?",
    "What is the mean of a dataset?",
    "What are similar triangles?",
    "What is the surface area of a cylinder?",
]

previous_results = _load_previous_results()
results: list[dict[str, Any]] = []

for query in benchmark_queries:
    baseline_entry = previous_results.get(query, {})
    current_router_result = _route_query(query)

    results.append(
        {
            "query": query,
            "previous_router_result": _extract_previous_router_result(baseline_entry),
            "new_router_result": current_router_result,
            "selected_chapter": current_router_result["selected_chapter"],
            "confidence_score": current_router_result["confidence_score"],
        }
    )

REPORT_PATH.write_text(json.dumps(results, indent=2))
print(json.dumps(results, indent=2))
