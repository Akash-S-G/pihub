from __future__ import annotations

import json
import re
import tarfile
import urllib.request
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


BASE_URL = "http://localhost:8030"
GRADE = 8
WORD_RE = re.compile(r"[A-Za-z0-9]+")
FORMULA_RE = re.compile(r"[A-Za-z0-9πθ°\s]{1,40}[=<>≤≥][A-Za-z0-9πθ°+\-*/×÷^().\s]{1,80}")

STOP_TERMS = {
    "activity",
    "chapter",
    "class",
    "curiosity",
    "example",
    "exercise",
    "figure",
    "ganita",
    "grade",
    "image",
    "images",
    "prakash",
    "question",
    "science",
    "table",
    "textbook",
}


@dataclass
class PilotPack:
    pack_id: str
    subject: str
    chapter: str
    status_code: int | None = None
    regenerated: bool | None = None
    response_pack_id: str | None = None


def normalize(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def words(text: Any) -> list[str]:
    return [token.lower() for token in WORD_RE.findall(str(text or "")) if len(token) >= 4 and token.lower() not in STOP_TERMS and not token.isdigit()]


def percent(value: int | float, total: int | float) -> float:
    if not total:
        return 100.0
    return round(100.0 * float(value) / float(total), 2)


def get_json(path: str) -> Any:
    with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def pack_dir(pack_record: dict[str, Any]) -> Path:
    manifest_path = pack_record.get("manifest_path")
    if manifest_path:
        return Path(str(manifest_path)).parent
    archive_path = Path(str(pack_record.get("archive_path") or ""))
    return archive_path.with_suffix("").with_suffix("")


def load_artifact(pack_record: dict[str, Any], filename: str) -> Any:
    return load_json(pack_dir(pack_record) / filename)


def load_report(pack_record: dict[str, Any], filename: str) -> dict[str, Any]:
    value = load_json(pack_dir(pack_record) / "reports" / filename)
    return value if isinstance(value, dict) else {}


def parse_pilot_rows(markdown_path: Path = Path("GRADE8_CONCEPT_PRESERVATION_REPORT.md")) -> list[PilotPack]:
    text = markdown_path.read_text(encoding="utf-8")
    match = re.search(r"## Regeneration\s+```json\s*(\{.*?\})\s*```", text, re.S)
    if not match:
        raise RuntimeError(f"Could not find regeneration JSON in {markdown_path}")
    payload = json.loads(match.group(1))
    rows = []
    for row in payload.get("rows", []):
        response = row.get("response") if isinstance(row.get("response"), dict) else {}
        rows.append(
            PilotPack(
                pack_id=str(row.get("pack_id")),
                subject=str(row.get("subject") or ""),
                chapter=str(row.get("chapter") or ""),
                status_code=row.get("status_code"),
                regenerated=row.get("regenerated"),
                response_pack_id=str(response.get("pack_id")) if response.get("pack_id") else None,
            )
        )
    return rows


def pack_records_for_pilot() -> list[tuple[PilotPack, dict[str, Any] | None]]:
    packs = get_json("/packs/list").get("packs", [])
    by_id = {str(pack.get("pack_id")): pack for pack in packs}
    records: list[tuple[PilotPack, dict[str, Any] | None]] = []
    for pilot in parse_pilot_rows():
        record = by_id.get(pilot.response_pack_id or "") or by_id.get(pilot.pack_id)
        records.append((pilot, record))
    return records


def representative_terms(text: str, limit: int = 30) -> list[str]:
    counts = Counter(words(text))
    return [term for term, _ in counts.most_common(limit)]


def extract_formulas(text: str) -> list[str]:
    formulas = []
    for item in FORMULA_RE.findall(text or ""):
        item = re.sub(r"\s+", " ", item).strip()
        if 3 <= len(item) <= 120:
            formulas.append(item)
    return list(dict.fromkeys(formulas))


def concept_present(concept: str, texts: list[str]) -> bool:
    concept_norm = normalize(concept)
    if not concept_norm:
        return True
    joined = normalize(" ".join(texts))
    if concept_norm in joined:
        return True
    concept_terms = set(words(concept))
    if not concept_terms:
        return True
    joined_terms = set(words(joined))
    return len(concept_terms & joined_terms) / max(1, len(concept_terms)) >= 0.65


def best_similarity(text: str, candidates: list[str]) -> float:
    source = normalize(text)
    if not source:
        return 0.0
    return max((SequenceMatcher(None, source, normalize(candidate)).ratio() for candidate in candidates), default=0.0)


def qdrant_query_chunks(grade: int, subject: str, chapter: str, language: str = "english") -> list[dict[str, Any]]:
    # Use the existing pack-service generator internals read-only: search only, no save.
    from app.pack_generator import PackGenerator

    generator = PackGenerator(
        qdrant_url="http://qdrant:6333",
        qdrant_collection="educational_chunks",
        pack_storage_path="/shared/packs",
        curriculum_graph_path="/shared/work/curriculum_graph.json",
    )
    import asyncio

    return asyncio.run(generator._search_chunks_by_metadata(grade=grade, subject=subject, chapter=chapter, language=language, limit=10000))


def archive_content_from_record(record: dict[str, Any]) -> list[dict[str, Any]]:
    content = load_artifact(record, "content.json")
    if isinstance(content, list):
        return content
    archive_path = Path(str(record.get("archive_path") or ""))
    if not archive_path.exists():
        return []
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            if member.name.endswith("/content.json"):
                file_obj = archive.extractfile(member)
                if file_obj is None:
                    return []
                return json.loads(file_obj.read().decode("utf-8"))
    return []
