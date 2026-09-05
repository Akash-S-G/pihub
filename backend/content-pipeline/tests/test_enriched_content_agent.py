from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from app.educational_intelligence.enriched_content_agent import (
    EnrichedContentAgent,
    TopicEnrichment,
)
from app.educational_intelligence.enrichment_store import EnrichmentStore
from app.educational_intelligence.web_resource_finder import (
    WebResource,
    WebResourceFinder,
)


class _StubArtifactAgent:
    async def generate_artifacts(self, chunks, max_iterations=None, skip_critique=False, pdf_path=None):
        return {
            "artifacts": {"glossary": [{"term": "Photosynthesis"}, {"term": "Chlorophyll"}]},
            "images": [], "formulas": [], "latex_block": "", "image_dir": "",
            "analysis": {"category": "science", "key_concepts": []}, "plan": ["glossary"],
        }


class _StubApplications:
    async def generate(self, chunks):
        return [{"concept": "Photosynthesis", "real_world_use": "crops", "explanation": "..."}]


class _StubWebFinder(WebResourceFinder):
    """Deterministic fake; no network. Tags resources with the requested language."""
    def __init__(self):
        super().__init__(timeout=1.0, max_per_topic=2)
        self.calls: list[tuple[str, str]] = []

    async def find(self, topic, language="en", subject=None):
        self.calls.append((topic, language))
        return type(
            "TR", (), {
                "videos": [WebResource(title=f"{topic} {language} video", url=f"http://v/{language}/{topic}", resource_type="video", source="YouTube", language=language, thumbnail=f"http://t/{language}/{topic}.jpg")],
                "articles": [WebResource(title=f"{topic} {language} article", url=f"http://a/{language}/{topic}", resource_type="article", source="web", language=language)],
                "references": [],
                "simulations": [WebResource(title=f"{topic} sim", url="http://phet.colorado.edu/x", resource_type="simulation", source="phet.colorado.edu", language=language)],
            }
        )()


def _make_agent(tmp_media: Path | None = None):
    agent = EnrichedContentAgent.__new__(EnrichedContentAgent)
    from app.educational_intelligence.agentic_orchestrator import ContentAnalyzer
    from app.educational_intelligence.multilingual_support import MultilingualSupport

    agent.artifact_agent = _StubArtifactAgent()
    agent.applications_generator = _StubApplications()
    agent.analyzer = ContentAnalyzer()
    agent.multilingual = MultilingualSupport()
    agent.web_finder = _StubWebFinder()
    agent.fetch_languages = ["en", "kn"]
    agent.max_videos_per_topic = 1
    agent.max_images_per_topic = 2
    # use a fake media store so no real downloads happen
    agent.media_store = _FakeMediaStore(tmp_media)
    agent.enrichment_store = None  # skip Qdrant unless test provides one
    agent._seen_topics_by_subject = {}
    return agent


class _FakeMediaStore:
    """Records store calls, writes a dummy file so local_path is non-empty."""
    def __init__(self, root=None):
        self.root = root or Path(tempfile.mkdtemp(prefix="hermes-media-"))
        (self.root / "videos").mkdir(parents=True, exist_ok=True)
        (self.root / "images").mkdir(parents=True, exist_ok=True)
        self.videos = []
        self.images = []
        self._seen: dict[str, set[str]] = {}

    async def store_video(self, url, title="", source="", language="en", topic=""):
        from app.educational_intelligence.media_store import StoredMedia
        p = self.root / "videos" / f"{abs(hash(url))}.mp4"
        p.write_bytes(b"FAKEMP4")
        self.videos.append((url, language))
        return StoredMedia(media_id="x", source_url=url, media_type="video", local_path=str(p),
                           title=title, source=source, language=language, topic=topic,
                           size_bytes=7, compressed=True)

    async def store_image(self, url, title="", source="", language="en", topic=""):
        from app.educational_intelligence.media_store import StoredMedia
        p = self.root / "images" / f"{abs(hash(url))}.jpg"
        p.write_bytes(b"FAKEIMG")
        self.images.append((url, language))
        return StoredMedia(media_id="y", source_url=url, media_type="image", local_path=str(p),
                           title=title, source=source, language=language, topic=topic,
                           size_bytes=7, compressed=False)

    # --- durable dedup API (in-memory for tests) ---
    def get_seen_topics(self, subject: str) -> list[str]:
        return list(self._seen.get(subject, set()))

    def mark_topic_seen(self, subject: str, topic_key: str) -> None:
        self._seen.setdefault(subject, set()).add(topic_key)

    def clear_subject_seen(self, subject=None) -> None:
        if subject is None:
            self._seen.clear()
        else:
            self._seen.pop(subject, None)


class EnrichedContentAgentTests(unittest.TestCase):
    def setUp(self):
        self.en_chunks = [{
            "text": "Photosynthesis is the process by which plants make food using chlorophyll and sunlight.",
            "metadata": {"chapter": "Nutrition in Plants", "subject": "science", "grade": 7,
                         "topics": ["photosynthesis", "chlorophyll"], "language": "en"}}]
        self.kn_chunks = [{
            "text": "ದ್ಯುತಿಸಂಶ್ಲೇಷಣೆ ಎಂಬುದು ಸಸ್ಯಗಳು ಆಹಾರವನ್ನು ತಯಾರಿಸುವ ಪ್ರಕ್ರಿಯೆ.",
            "metadata": {"chapter": "ಸಸ್ಯಗಳಲ್ಲಿ ಪೋಷಣೆ", "subject": "science", "grade": 7}}]

    def test_bilingual_fetch(self):
        agent = _make_agent()
        result = asyncio.run(agent.generate(self.en_chunks, skip_critique=True, include_web=True))
        # the stub was asked for both en and kn per topic
        langs = {lang for (_t, lang) in agent.web_finder.calls}
        self.assertEqual(langs, {"en", "kn"})
        block = result["topic_enrichment"][0]
        vid_langs = {v["language"] for v in block["videos"]}
        self.assertEqual(vid_langs, {"en", "kn"})
        self.assertIn("kn", result["fetch_languages"])

    def test_media_downloaded_and_local_path_set(self):
        agent = _make_agent()
        result = asyncio.run(agent.generate(self.en_chunks, skip_critique=True, include_web=True, download_media=True))
        block = result["topic_enrichment"][0]
        # capped to 1 video per topic (max_videos_per_topic=1)
        downloaded = [v for v in block["videos"] if v.get("offline_available")]
        self.assertTrue(downloaded)
        self.assertTrue(downloaded[0]["local_path"].endswith(".mp4"))
        self.assertTrue(downloaded[0]["compressed"])
        self.assertGreaterEqual(result["enrichment_summary"]["videos_downloaded"], 1)

    def test_web_disabled_no_media(self):
        agent = _make_agent()
        result = asyncio.run(agent.generate(self.en_chunks, skip_critique=True, include_web=False))
        self.assertEqual(agent.media_store.videos, [])

    def test_kannada_language_detected(self):
        agent = _make_agent()
        result = asyncio.run(agent.generate(self.kn_chunks, skip_critique=True, include_web=True))
        self.assertEqual(result["language"], "kn")

    def test_topics_unique_within_chapter(self):
        agent = _make_agent()
        result = asyncio.run(agent.generate(self.en_chunks, skip_critique=True, include_web=False))
        lowered = [t.lower() for t in result["topics"]]
        self.assertEqual(len(lowered), len(set(lowered)))

    def test_dedupe_across_subject(self):
        agent = _make_agent()
        r1 = asyncio.run(agent.generate(self.en_chunks, skip_critique=True, include_web=False))
        r2 = asyncio.run(agent.generate(self.en_chunks, skip_critique=True, include_web=False, dedupe_across_subject=True))
        overlap = set(t.lower() for t in r1["topics"]) & set(t.lower() for t in r2["topics"])
        self.assertEqual(overlap, set())


class EnrichmentStoreFlatTests(unittest.TestCase):
    def test_flatten(self):
        te = [{"topic": "X", "language": "en", "videos": [{"title": "v", "url": "u", "language": "en", "source": "s", "resource_type": "video", "thumbnail": "t.jpg"}],
               "articles": [], "references": [], "simulations": [{"title": "s", "url": "u2", "language": "kn", "resource_type": "simulation", "source": "phet"}]}]
        rw = [{"concept": "X", "real_world_use": "crops", "explanation": "uses sunlight"}]
        recs = EnrichmentStore.flatten_topic_enrichment(te, rw, {"subject": "science", "chapter": "c", "grade": 7, "language": "en"})
        types = {r["resource_type"] for r in recs}
        self.assertEqual(types, {"video", "simulation", "real_world_example"})
        vid = next(r for r in recs if r["resource_type"] == "video")
        self.assertEqual(vid["subject"], "science")
        self.assertEqual(vid["topic"], "X")
        self.assertEqual(vid["language"], "en")


class MediaStoreMockTests(unittest.TestCase):
    def test_local_path_and_compressed_flag(self):
        store = _FakeMediaStore()
        media = asyncio.run(store.store_video("http://x/1", title="t", language="kn", topic="X"))
        self.assertTrue(media.local_path.endswith(".mp4"))
        self.assertTrue(media.compressed)


if __name__ == "__main__":
    unittest.main()
