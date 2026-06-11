from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import resource
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.content_generation import DoclingPdfExtractor, SectionBuilder


BENCHMARKS = [
    {
        "name": "grade8_science",
        "metadata": {"grade": 8, "subject": "science", "chapter": "Force and Pressure", "language": "english"},
        "text": """
Force and Pressure

Force is a push or pull acting on an object. A force can change the speed, direction, or shape of an object.
Pressure is the force acting per unit area. Pressure = Force / Area. When the same force acts on a smaller
area, the pressure is greater. For example, a sharp nail enters wood more easily than a blunt nail because
the sharp tip has a smaller area and therefore produces greater pressure.

Fluids also exert pressure. Air pressure acts in all directions. Students should remember that pressure
depends on both force and area, not force alone.
""",
    },
    {
        "name": "grade9_mathematics",
        "metadata": {"grade": 9, "subject": "mathematics", "chapter": "Linear Equations", "language": "english"},
        "text": """
Linear Equations in Two Variables

A linear equation in two variables is an equation that can be written as ax + by + c = 0, where a, b, and c
are real numbers and a and b are not both zero. Each solution is an ordered pair. The graph of a linear
equation in two variables is a straight line.

For example, x + y = 5 has solutions such as (1, 4), (2, 3), and (5, 0). These points lie on the same line.
""",
    },
    {
        "name": "grade10_biology",
        "metadata": {"grade": 10, "subject": "biology", "chapter": "Life Processes", "language": "english"},
        "text": """
Life Processes

Photosynthesis is the process by which green plants prepare food using carbon dioxide, water, and sunlight.
Chlorophyll captures light energy. The word equation is carbon dioxide + water -> glucose + oxygen.
This process is important because it provides food for plants and releases oxygen into the atmosphere.

Respiration releases energy from food. Plants and animals both respire, but only green plants perform
photosynthesis.
""",
    },
]


SCHEMAS = {
    "summary": {
        "title": "string",
        "summary": "string",
        "keyPoints": ["string"],
        "importantFacts": ["string"],
    },
    "flashcards": {
        "items": [{"question": "string", "answer": "string", "difficulty": "easy|medium|hard"}],
    },
    "quiz": {
        "items": [{"question": "string", "options": ["string", "string", "string", "string"], "answer": "string", "explanation": "string"}],
    },
    "glossary": {
        "items": [{"term": "string", "definition": "string"}],
    },
    "learning_objectives": {
        "items": [{"objective": "string"}],
    },
}


@dataclass
class GenerationRecord:
    benchmark: str
    section_id: str
    artifact: str
    model_name: str
    quantization: str
    prompt_length: int
    response_length: int
    latency_seconds: float
    retry_count: int
    json_valid: bool
    cache_hit: bool
    output: Any
    error: str = ""


class LlamaCppGemmaValidator:
    def __init__(self, llama_cli: Path, model_path: Path, out_dir: Path, retries: int = 3) -> None:
        self.llama_cli = llama_cli
        self.model_path = model_path
        self.out_dir = out_dir
        self.retries = retries
        self.cache_dir = out_dir / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.model_name = model_path.name
        self.quantization = self._quantization(model_path.name)

    def generate(self, benchmark: str, section: Any, artifact: str) -> GenerationRecord:
        prompt = self._prompt(section, artifact)
        cache_key = hashlib.sha256(f"{self.model_path}:{artifact}:{prompt}".encode("utf-8")).hexdigest()
        cache_path = self.cache_dir / f"{cache_key}.json"
        if cache_path.exists():
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            return GenerationRecord(
                benchmark=benchmark,
                section_id=section.section_id,
                artifact=artifact,
                model_name=self.model_name,
                quantization=self.quantization,
                prompt_length=len(prompt),
                response_length=len(json.dumps(cached)),
                latency_seconds=0.0,
                retry_count=0,
                json_valid=True,
                cache_hit=True,
                output=cached,
            )

        last_error = ""
        started = time.perf_counter()
        for attempt in range(1, self.retries + 1):
            attempt_prompt = prompt
            if attempt > 1:
                attempt_prompt += f"\n\nPrevious output was invalid JSON: {last_error}. Return corrected JSON only."
            response_started = time.perf_counter()
            completed = subprocess.run(
                [
                    str(self.llama_cli),
                    "-m",
                    str(self.model_path),
                    "-p",
                    attempt_prompt,
                    "-n",
                    "450",
                    "--jinja",
                    "--single-turn",
                    "--reasoning",
                    "off",
                    "--reasoning-budget",
                    "0",
                    "--temp",
                    "0.2",
                    "--top-p",
                    "0.9",
                    "--ctx-size",
                    "4096",
                    "--no-display-prompt",
                    "--simple-io",
                    "--no-warmup",
                ],
                cwd=str(self.out_dir),
                text=True,
                capture_output=True,
                timeout=150,
            )
            raw = (completed.stdout or "").strip()
            if completed.returncode != 0:
                last_error = (completed.stderr or completed.stdout or f"returncode={completed.returncode}")[:1000]
                continue
            try:
                parsed = None
                validation_error = ""
                for candidate in reversed(self._extract_json_candidates(raw)):
                    try:
                        self._validate_artifact(artifact, candidate)
                        parsed = candidate
                        break
                    except Exception as exc:
                        validation_error = str(exc)
                if parsed is None:
                    raise ValueError(validation_error or "no valid JSON artifact found")
                cache_path.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
                return GenerationRecord(
                    benchmark=benchmark,
                    section_id=section.section_id,
                    artifact=artifact,
                    model_name=self.model_name,
                    quantization=self.quantization,
                    prompt_length=len(attempt_prompt),
                    response_length=len(raw),
                    latency_seconds=round(time.perf_counter() - response_started, 3),
                    retry_count=attempt - 1,
                    json_valid=True,
                    cache_hit=False,
                    output=parsed,
                )
            except Exception as exc:
                last_error = str(exc)

        return GenerationRecord(
            benchmark=benchmark,
            section_id=section.section_id,
            artifact=artifact,
            model_name=self.model_name,
            quantization=self.quantization,
            prompt_length=len(prompt),
            response_length=0,
            latency_seconds=round(time.perf_counter() - started, 3),
            retry_count=self.retries,
            json_valid=False,
            cache_hit=False,
            output={},
            error=last_error,
        )

    def _prompt(self, section: Any, artifact: str) -> str:
        schema = json.dumps(SCHEMAS[artifact], ensure_ascii=False)
        return (
            "You are generating school learning artifacts from one source textbook section.\n"
            "Use only the source text. Do not invent facts. Return valid JSON only. No markdown.\n"
            "Do not include reasoning, commentary, channel tags, or explanations outside JSON.\n"
            f"Artifact: {artifact}\n"
            f"Required JSON schema example: {schema}\n"
            f"Section title: {section.title}\n"
            f"Source section:\n{section.content[:9000]}\n"
        )

    @staticmethod
    def _extract_json_candidates(text: str) -> list[Any]:
        value = text.strip()
        value = re.sub(r"^```(?:json)?", "", value, flags=re.I).strip()
        value = re.sub(r"```$", "", value).strip()
        decoder = json.JSONDecoder()
        candidates: list[Any] = []
        try:
            candidates.append(json.loads(value))
        except json.JSONDecodeError:
            pass
        starts = [index for index, char in enumerate(value) if char in "[{"]
        for start in starts:
            try:
                parsed, _ = decoder.raw_decode(value[start:])
                candidates.append(parsed)
            except json.JSONDecodeError:
                continue
        return candidates

    @staticmethod
    def _validate_artifact(artifact: str, parsed: Any) -> None:
        if artifact == "summary":
            if not all(parsed.get(key) for key in ("title", "summary")):
                raise ValueError("summary missing title or summary")
            return
        items = parsed.get("items") if isinstance(parsed, dict) else None
        if not isinstance(items, list) or not items:
            raise ValueError(f"{artifact} missing non-empty items")
        if artifact == "quiz":
            for item in items:
                if len(item.get("options") or []) != 4 or not item.get("answer") or not item.get("explanation"):
                    raise ValueError("quiz item missing options/answer/explanation")

    @staticmethod
    def _quantization(name: str) -> str:
        match = re.search(r"(Q\d(?:_[A-Z]+)*(?:_[A-Z]+)?|UD_Q\d_[A-Z_]+)", name, re.I)
        return match.group(1) if match else "unknown"


def score_artifact(source_text: str, artifact: str, output: Any) -> dict[str, Any]:
    text = json.dumps(output, ensure_ascii=False)
    source_terms = content_terms(source_text)
    output_terms = content_terms(text)
    unsupported = sorted(term for term in output_terms if term not in source_terms and len(term) > 4)[:30]
    coverage = len(output_terms & source_terms) / max(1, len(source_terms))
    hallucination_risk = min(1.0, len(unsupported) / max(1, len(output_terms)))
    readability = 1.0 if 80 <= average_sentence_length(text) <= 220 else 0.75
    usefulness = 1.0 if output_terms & source_terms else 0.2
    accuracy = 1.0 - hallucination_risk
    return {
        "artifact": artifact,
        "accuracy": round(accuracy * 100, 2),
        "educational_usefulness": round(usefulness * 100, 2),
        "hallucination_risk": round(hallucination_risk * 100, 2),
        "coverage": round(min(1.0, coverage) * 100, 2),
        "readability": round(readability * 100, 2),
        "unsupported_terms": unsupported,
    }


def content_terms(text: str) -> set[str]:
    stop = {"this", "that", "with", "from", "section", "source", "text", "question", "answer", "explanation"}
    return {match.lower() for match in re.findall(r"\b[a-zA-Z][a-zA-Z]{3,}(?:\s+[a-zA-Z][a-zA-Z]{3,}){0,2}\b", text) if match.lower() not in stop}


def average_sentence_length(text: str) -> float:
    sentences = [part for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    if not sentences:
        return 0.0
    return sum(len(sentence) for sentence in sentences) / len(sentences)


def markdown_artifact_preview(title: str, value: Any) -> str:
    return f"### {title}\n\n```json\n{json.dumps(value, indent=2, ensure_ascii=False)[:6000]}\n```\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--llama-cli", default=os.getenv("LLAMA_CPP_CLI", "/tmp/llama-gemma-build/bin/llama-completion"))
    parser.add_argument("--model", default=os.getenv("GEMMA_MODEL_PATH", "/home/akash/Downloads/5th sem data/gemma-4-E2B-it-Q4_K_M.gguf"))
    parser.add_argument("--out-dir", default="content_quality_1_model_validation")
    args = parser.parse_args()

    llama_cli = Path(args.llama_cli)
    model_path = Path(args.model)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    extractor = DoclingPdfExtractor()
    section_builder = SectionBuilder(min_words=80, max_words=400)
    validator = LlamaCppGemmaValidator(llama_cli, model_path, out_dir)

    records: list[GenerationRecord] = []
    audit_rows: list[dict[str, Any]] = []
    source_sections: dict[str, str] = {}
    started = time.perf_counter()
    fatal_error = ""

    if not llama_cli.exists():
        fatal_error = f"llama.cpp CLI not found: {llama_cli}"
    elif not model_path.exists():
        fatal_error = f"Gemma model not found: {model_path}"

    if not fatal_error:
        for benchmark in BENCHMARKS:
            document = extractor.extract_text(benchmark["text"], source_path=benchmark["name"], metadata=benchmark["metadata"])
            sections = section_builder.build(document)
            for section in sections:
                source_sections[f"{benchmark['name']}:{section.section_id}"] = section.content
                for artifact in SCHEMAS:
                    record = validator.generate(benchmark["name"], section, artifact)
                    records.append(record)
                    if record.json_valid:
                        audit_rows.append(score_artifact(section.content, artifact, record.output))
                    else:
                        audit_rows.append({"artifact": artifact, "accuracy": 0, "educational_usefulness": 0, "hallucination_risk": 100, "coverage": 0, "readability": 0, "unsupported_terms": [], "error": record.error})

    total = len(records)
    invalid = sum(1 for record in records if not record.json_valid)
    fallback_used = False
    model_generated = bool(records) and any(not record.cache_hit and record.json_valid for record in records)
    json_failure_rate = invalid / max(1, total)
    hallucination_rate = sum(row.get("hallucination_risk", 100) for row in audit_rows) / max(1, len(audit_rows))
    average_latency = sum(record.latency_seconds for record in records) / max(1, len([record for record in records if not record.cache_hit]))
    peak_ram_mb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024
    end_to_end = time.perf_counter() - started

    certification_failures = []
    if fatal_error:
        certification_failures.append(fatal_error)
    if not model_generated:
        certification_failures.append("model_generation_skipped_or_failed")
        first_error = next((record.error for record in records if record.error), "")
        if first_error:
            certification_failures.append(first_error.splitlines()[0][:240])
    if fallback_used:
        certification_failures.append("fallback_used")
    if json_failure_rate > 0.10:
        certification_failures.append("json_validation_failure_rate>10%")
    if hallucination_rate > 20:
        certification_failures.append("hallucination_rate_unacceptable")

    records_json = [
        {
            **record.__dict__,
            "output": record.output,
        }
        for record in records
    ]
    (out_dir / "generation_records.json").write_text(json.dumps(records_json, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "quality_audit.json").write_text(json.dumps(audit_rows, indent=2, ensure_ascii=False), encoding="utf-8")

    validation_md = ["# CONTENT QUALITY 1 Model Validation\n", f"Model: `{model_path}`\n", f"llama.cpp: `{llama_cli}`\n", f"Fatal error: `{fatal_error or 'none'}`\n"]
    for record in records:
        if record.json_valid:
            validation_md.append(f"## {record.benchmark} / {record.section_id} / {record.artifact}\n")
            validation_md.append(f"Prompt length: {record.prompt_length}; response length: {record.response_length}; latency: {record.latency_seconds}s; retries: {record.retry_count}; cache_hit: {record.cache_hit}\n")
            validation_md.append(markdown_artifact_preview(record.artifact, record.output))
        else:
            validation_md.append(f"## FAILED {record.benchmark} / {record.section_id} / {record.artifact}\n\n`{record.error}`\n")
    Path("CONTENT_QUALITY_1_MODEL_VALIDATION.md").write_text("\n".join(validation_md), encoding="utf-8")

    quality_md = ["# CONTENT QUALITY 1 Quality Audit\n"]
    for row in audit_rows:
        quality_md.append(f"- {row.get('artifact')}: accuracy={row.get('accuracy')} usefulness={row.get('educational_usefulness')} hallucination_risk={row.get('hallucination_risk')} coverage={row.get('coverage')} readability={row.get('readability')}")
    Path("CONTENT_QUALITY_1_QUALITY_AUDIT.md").write_text("\n".join(quality_md) + "\n", encoding="utf-8")

    hallucination_md = ["# CONTENT QUALITY 1 Hallucination Report\n"]
    for row in audit_rows:
        unsupported = row.get("unsupported_terms") or []
        if unsupported or row.get("error"):
            hallucination_md.append(f"- {row.get('artifact')}: unsupported={unsupported} error={row.get('error', '')}")
    if len(hallucination_md) == 1:
        hallucination_md.append("No unsupported terms detected by lexical source audit.")
    Path("CONTENT_QUALITY_1_HALLUCINATION_REPORT.md").write_text("\n".join(hallucination_md) + "\n", encoding="utf-8")

    perf = {
        "average_generation_time_per_section": round(average_latency, 3),
        "average_tokens_per_second": "unavailable_from_llama_cli_stdout",
        "peak_ram_mb": round(peak_ram_mb, 2),
        "cache_hits": sum(1 for record in records if record.cache_hit),
        "cache_misses": sum(1 for record in records if not record.cache_hit),
        "end_to_end_pack_generation_time": round(end_to_end, 3),
    }
    Path("CONTENT_QUALITY_1_PERFORMANCE_REPORT.md").write_text("# CONTENT QUALITY 1 Performance Report\n\n```json\n" + json.dumps(perf, indent=2) + "\n```\n", encoding="utf-8")

    final = {
        "did_gemma_generate_content": model_generated,
        "fallback_used": fallback_used,
        "json_failure_rate": round(json_failure_rate, 4),
        "hallucination_rate": round(hallucination_rate, 2),
        "quality_superior_to_deterministic_generation": "unproven_without_successful_model_run" if fatal_error else "requires_human_review",
        "production_ready": not certification_failures,
        "certification_failures": certification_failures,
    }
    Path("CONTENT_QUALITY_1_FINAL_CERTIFICATION.md").write_text("# CONTENT QUALITY 1 Final Certification\n\n```json\n" + json.dumps(final, indent=2) + "\n```\n", encoding="utf-8")
    return 1 if certification_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
