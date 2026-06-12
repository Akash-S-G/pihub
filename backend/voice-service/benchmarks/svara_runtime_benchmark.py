from __future__ import annotations

import asyncio
import json
import resource
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import get_runtime_settings  # noqa: E402
from tts.providers import SvaraLocalProvider  # noqa: E402


CASES = [
    {
        "name": "english_photosynthesis",
        "language": "en",
        "text": "Photosynthesis is the process by which plants make food using sunlight, water, and carbon dioxide.",
    },
    {
        "name": "hindi_photosynthesis",
        "language": "hi",
        "text": "प्रकाश संश्लेषण वह प्रक्रिया है जिसके द्वारा पौधे सूर्य के प्रकाश से भोजन बनाते हैं।",
    },
    {
        "name": "kannada_photosynthesis",
        "language": "kn",
        "text": "ದ್ಯುತಿಸಂಶ್ಲೇಷಣೆ ಎಂಬುದು ಸಸ್ಯಗಳು ಸೂರ್ಯನ ಬೆಳಕನ್ನು ಬಳಸಿ ಆಹಾರ ತಯಾರಿಸುವ ಪ್ರಕ್ರಿಯೆ.",
    },
    {
        "name": "code_switching_photosynthesis",
        "language": "hi",
        "text": "Photosynthesis mein plants sunlight use karke apna food banate hain.",
    },
]


async def main() -> None:
    provider = SvaraLocalProvider(get_runtime_settings())
    rows: list[dict[str, object]] = []
    load_start = time.perf_counter()
    await provider.warmup()
    load_ms = round((time.perf_counter() - load_start) * 1000, 2)

    for case in CASES:
        started = time.perf_counter()
        result = await provider.synthesize(case["text"], case["language"])
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        duration_sec = max(result.duration_ms / 1000, 0.001)
        rows.append(
            {
                **case,
                "generation_time_ms": elapsed_ms,
                "audio_duration_ms": result.duration_ms,
                "rtf": round((elapsed_ms / 1000) / duration_sec, 3),
                "file_size_bytes": result.file_size_bytes,
                "peak_ram_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2),
                "audio_file": result.file_path,
            }
        )

    await provider.close()
    report_path = ROOT / "SVARA_RUNTIME_BENCHMARK.md"
    report = [
        "# Svara Local Provider Benchmark",
        "",
        f"Warmup/load path completed in `{load_ms}` ms.",
        "",
        "| Case | Language | Generation ms | Audio ms | RTF | File bytes | Peak RAM MB |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        report.append(
            f"| {row['name']} | {row['language']} | {row['generation_time_ms']} | "
            f"{row['audio_duration_ms']} | {row['rtf']} | {row['file_size_bytes']} | {row['peak_ram_mb']} |"
        )
    report.append("")
    report.append("```json")
    report.append(json.dumps(rows, ensure_ascii=False, indent=2))
    report.append("```")
    report_path.write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"load_ms": load_ms, "cases": rows}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
