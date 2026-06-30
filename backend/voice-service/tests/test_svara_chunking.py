from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tts.providers.svara_local_provider import SvaraLocalProvider  # noqa: E402


def test_chunk_text_prefers_sentence_boundaries() -> None:
    text = (
        "Photosynthesis converts sunlight into energy. "
        "Plants use water and carbon dioxide to make glucose. "
        "This process supports most life on Earth."
    )

    chunks = SvaraLocalProvider._chunk_text(text, max_chars=60)

    assert len(chunks) >= 3
    assert all(len(chunk) <= 60 for chunk in chunks)
    assert chunks[0].endswith(".")
    assert chunks[-1].endswith(".")


def test_chunk_text_splits_long_unpunctuated_segments() -> None:
    text = " ".join(["phonetics"] * 40)

    chunks = SvaraLocalProvider._chunk_text(text, max_chars=40)

    assert len(chunks) > 1
    assert all(len(chunk) <= 40 for chunk in chunks)


def test_chunk_text_splits_long_clauses_before_words() -> None:
    text = (
        "The water cycle moves water from oceans to land, then into the air, "
        "and later back to the ground through rain and runoff."
    )

    chunks = SvaraLocalProvider._chunk_text(text, max_chars=55)

    assert len(chunks) >= 2
    assert all(len(chunk) <= 55 for chunk in chunks)
    assert any("," in chunk for chunk in chunks)
