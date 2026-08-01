from __future__ import annotations

"""Enriched content agent for the content-pipeline.

A NEW agent (kept separate from :class:`ArtifactAgent`) that produces the
existing textbook-based artifacts AND layers three enrichment features on top,
per topic in the chapter:

    1. Related videos   -> web search across YouTube + open web.
    2. Real-world usage -> concept-grounded applications + web articles.
    3. Simulations      -> local PhET catalog / enrichment registry matches.

It supports English and Kannada (and other Indian-script) textbooks by detecting
the source language and threading it through generation and resource lookups.

Design principle: COMPOSE existing components, never fork them.
    * base artifacts        -> app.educational_intelligence.ArtifactAgent (reused)
    * real-world examples   -> app.educational_intelligence.ApplicationsGenerator (reused)
    * language detection    -> app.educational_intelligence.MultilingualSupport (reused)
    * videos / articles / simulations -> WebResourceFinder (new, open-web search)

Simulations are discovered from the OPEN WEB (PhET, OLabs, GeoGebra, JavaLab,
etc.) via WebResourceFinder. The existing local PhET catalog, EnrichmentRouter,
and their endpoint are left untouched.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from app.educational_intelligence.agentic_orchestrator import ArtifactAgent, ContentAnalyzer
from app.educational_intelligence.applications_generator import ApplicationsGenerator
from app.educational_intelligence.artifact_cleaning import clean_text
from app.educational_intelligence.enrichment_store import EnrichmentStore
from app.educational_intelligence.inference_client import InferenceClient
from app.educational_intelligence.media_store import MediaStore
from app.educational_intelligence.multilingual_support import MultilingualSupport
from app.educational_intelligence.web_resource_finder import WebResourceFinder
from shared.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class TopicEnrichment:
    topic: str
    language: str = "en"
    videos: list[dict[str, Any]] = field(default_factory=list)
    articles: list[dict[str, Any]] = field(default_factory=list)
    references: list[dict[str, Any]] = field(default_factory=list)
    simulations: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "language": self.language,
            "videos": self.videos,
            "articles": self.articles,
            "references": self.references,
            "simulations": self.simulations,
        }


class EnrichedContentAgent:
    """Textbook artifact generation + per-topic web/real-world/simulation enrichment."""

    def __init__(
        self,
        inference_client: InferenceClient | None = None,
        artifact_agent: ArtifactAgent | None = None,
        web_finder: WebResourceFinder | None = None,
        media_store: MediaStore | None = None,
        enrichment_store: EnrichmentStore | None = None,
    ) -> None:
        self.inference = inference_client or InferenceClient()
        self.artifact_agent = artifact_agent or ArtifactAgent(inference_client=self.inference)
        self.applications_generator = ApplicationsGenerator(inference_client=self.inference)
        self.analyzer = ContentAnalyzer()
        self.multilingual = MultilingualSupport()
        self.web_finder = web_finder or WebResourceFinder()
        self.media_store = media_store  # may be None (constructed lazily by caller)
        self.enrichment_store = enrichment_store  # may be None (needs embedding model)
        settings = get_settings()
        self.fetch_languages = [
            lang.strip().lower()
            for lang in settings.enrichment_languages.split(",")
            if lang.strip()
        ] or ["en"]
        self.max_videos_per_topic = settings.media_max_videos_per_topic
        self.max_images_per_topic = settings.media_max_images_per_topic
        # Tracks topics already enriched, keyed by subject, so the same important
        # topic is never enriched twice across chapters of the same subject.
        # { subject_key: set(topic_key) }
        self._seen_topics_by_subject: dict[str, set[str]] = {}

    def reset_seen_topics(self, subject: str | None = None) -> None:
        """Clear the cross-chapter dedup memory (all subjects, or one subject)."""
        if subject is None:
            self._seen_topics_by_subject.clear()
        else:
            self._seen_topics_by_subject.pop(self._subject_key(subject), None)

    @staticmethod
    def _subject_key(subject: str | None) -> str:
        return (subject or "_default").strip().lower()

    def _collect_existing_seen(self, subject_key: str) -> list[str]:
        """Union of in-memory seen topics and the durable Mongo store."""
        seen = set(self._seen_topics_by_subject.get(subject_key, set()))
        if self.media_store is not None:
            for t in self.media_store.get_seen_topics(subject_key):
                seen.add(t)
        return list(seen)

    async def generate(
        self,
        chunks: list[dict[str, Any]],
        max_iterations: int | None = None,
        skip_critique: bool = False,
        pdf_path: str | None = None,
        max_topics: int = 8,
        include_web: bool = True,
        dedupe_across_subject: bool = True,
        download_media: bool = True,
        persist: bool = True,
        fetch_languages: list[str] | None = None,
    ) -> dict[str, Any]:
        """Full enriched generation.

        Returns a dict with the base artifact-agent output plus a
        ``topic_enrichment`` list and a ``real_world_examples`` block.

        Topics are the *important* topics of the chapter, de-duplicated within
        the chapter and (when ``dedupe_across_subject`` is True) across all
        previously processed chapters of the same subject, so no topic is
        enriched twice for a subject.

        Enrichment is fetched for every language in ``fetch_languages`` (defaults
        to the configured set, e.g. Kannada + English), media is downloaded +
        compressed for offline use when ``download_media`` is set, and records are
        persisted to Qdrant (+ media metadata to MongoDB) when ``persist`` is set.
        """
        # 1) language detection (source of truth = actual chapter text)
        all_text = " ".join(
            clean_text(str(c.get("text", ""))) for c in chunks if c.get("text")
        )
        metadata = chunks[0].get("metadata", {}) if chunks else {}
        language = self._resolve_language(all_text, metadata)
        # thread the detected language into chunk metadata so downstream
        # generators localize correctly
        for chunk in chunks:
            chunk.setdefault("metadata", {}).setdefault("language", language)

        subject = metadata.get("subject")

        # 2) base artifacts (reuse existing agent, unchanged)
        base = await self.artifact_agent.generate_artifacts(
            chunks=chunks,
            max_iterations=max_iterations,
            skip_critique=skip_critique,
            pdf_path=pdf_path,
        )

        # 3) determine the topics to enrich (important, de-duplicated within the
        # chapter and across the subject)
        analysis = self.analyzer.analyze(chunks)
        subject_key = self._subject_key(subject)
        # Cross-subject dedup is backed by Mongo (survives restarts) AND an
        # in-memory set (fast path within a single process run).
        subject_seen: set[str] = set()
        if dedupe_across_subject:
            subject_seen = self._seen_topics_by_subject.setdefault(subject_key, set())
            if self.media_store is not None:
                # hydrate from durable store
                for t in self._collect_existing_seen(subject_key):
                    subject_seen.add(t)
        topics = self._collect_topics(analysis, base, metadata, max_topics, subject_seen)
        # record the topics we chose so future chapters of this subject skip them
        for t in topics:
            tkey = t.lower()
            subject_seen.add(tkey)
            if dedupe_across_subject and self.media_store is not None:
                self.media_store.mark_topic_seen(subject_key, tkey)
        logger.info("Enriching %d topics (lang=%s): %s", len(topics), language, topics)

        # 4) real-world examples (chapter-level, reuse ApplicationsGenerator)
        real_world = await self.applications_generator.generate(chunks)

        # 5) resolve the languages to fetch (always include the chapter language)
        langs = fetch_languages or list(self.fetch_languages)
        if language not in langs:
            langs = [language] + langs
        # de-dup preserving order
        seen_l: set[str] = set()
        langs = [l for l in langs if not (l in seen_l or seen_l.add(l))]

        # 6) per-topic enrichment (bilingual videos + articles + simulations),
        # concurrently; media downloaded + compressed for offline access
        enrichment_tasks = [
            self._enrich_topic(topic, langs, subject, include_web, download_media)
            for topic in topics
        ]
        topic_enrichment = await asyncio.gather(*enrichment_tasks, return_exceptions=True)
        enriched: list[dict[str, Any]] = []
        for topic, res in zip(topics, topic_enrichment):
            if isinstance(res, TopicEnrichment):
                enriched.append(res.to_dict())
            else:
                logger.warning("Enrichment failed for topic %s: %s", topic, str(res)[:200])
                enriched.append(TopicEnrichment(topic=topic, language=",".join(langs)).to_dict())

        await self.web_finder.close()

        # 7) persist enrichment records to Qdrant for offline semantic retrieval
        persisted = 0
        if persist and self.enrichment_store is not None:
            records = EnrichmentStore.flatten_topic_enrichment(
                enriched, real_world,
                base_meta={
                    "subject": subject, "chapter": metadata.get("chapter"),
                    "grade": metadata.get("grade"), "language": language,
                },
            )
            persisted = await asyncio.to_thread(self.enrichment_store.store, records)

        return {
            **base,
            "language": language,
            "fetch_languages": langs,
            "topics": topics,
            "real_world_examples": real_world,
            "topic_enrichment": enriched,
            "enrichment_summary": {
                "topic_count": len(topics),
                "fetch_languages": langs,
                "total_videos": sum(len(t["videos"]) for t in enriched),
                "total_articles": sum(len(t["articles"]) for t in enriched),
                "total_simulations": sum(len(t["simulations"]) for t in enriched),
                "videos_downloaded": sum(
                    1 for t in enriched for v in t["videos"] if v.get("offline_available")
                ),
                "records_persisted": persisted,
                "web_enrichment_enabled": include_web and self.web_finder.enabled,
                "media_download_enabled": download_media and self.media_store is not None,
            },
        }

    async def _enrich_topic(
        self, topic: str, languages: list[str], subject: str | None, include_web: bool, download_media: bool
    ) -> TopicEnrichment:
        result = TopicEnrichment(topic=topic, language=",".join(languages))
        if not include_web:
            return result

        web = await self.web_finder.find_multi(topic, languages, subject=subject)
        result.videos = [v.to_dict() for v in web.videos]
        result.articles = [a.to_dict() for a in web.articles]
        result.references = [r.to_dict() for r in web.references]
        result.simulations = [s.to_dict() for s in web.simulations]

        # download + compress a bounded number of videos/images for offline use
        if download_media and self.media_store is not None:
            await self._download_topic_media(topic, result)
        return result

    async def _download_topic_media(self, topic: str, result: TopicEnrichment) -> None:
        store = self.media_store
        if store is None:
            return
        # videos: cap per topic; attach local_path + compression info in place
        for video in result.videos[: self.max_videos_per_topic]:
            media = await store.store_video(
                url=video.get("url", ""), title=video.get("title", ""),
                source=video.get("source", ""), language=video.get("language", "en"), topic=topic,
            )
            video["local_path"] = media.local_path
            video["offline_available"] = bool(media.local_path and not media.error)
            video["compressed"] = media.compressed
            if media.error:
                video["media_error"] = media.error
        # images: prefer article/reference thumbnails
        thumb_sources = [
            item for item in (result.references + result.articles + result.videos)
            if item.get("thumbnail")
        ]
        for item in thumb_sources[: self.max_images_per_topic]:
            media = await store.store_image(
                url=item.get("thumbnail", ""), title=item.get("title", ""),
                source=item.get("source", ""), language=item.get("language", "en"), topic=topic,
            )
            if media.local_path and not media.error:
                item["thumbnail_local_path"] = media.local_path

    def _resolve_language(self, text: str, metadata: dict[str, Any]) -> str:
        declared = str(metadata.get("language") or "").strip().lower()
        if declared in {"en", "kn", "hi", "ta", "te", "ml"}:
            return declared
        profile = self.multilingual.detect_language(text)
        if profile.confidence >= 0.5 and profile.language != "und":
            return profile.language
        return declared or "en"

    def _collect_topics(
        self,
        analysis: Any,
        base: dict[str, Any],
        metadata: dict[str, Any],
        max_topics: int,
        subject_seen: set[str] | None = None,
    ) -> list[str]:
        seen: set[str] = set()
        subject_seen = subject_seen if subject_seen is not None else set()
        topics: list[str] = []

        def _add(candidate: Any) -> None:
            if not candidate:
                return
            t = clean_text(str(candidate)).strip()
            key = t.lower()
            # skip if seen in this chapter OR already enriched for this subject
            if t and key not in seen and key not in subject_seen and len(t) > 2:
                seen.add(key)
                topics.append(t)

        # explicit curriculum metadata first
        for t in (metadata.get("topics") or []):
            _add(t)
        for c in (metadata.get("concepts") or []):
            _add(c)
        # analysis-derived key concepts
        for c in (analysis.key_concepts or []):
            _add(c)
        # glossary terms from base artifacts are high-quality topic anchors
        for entry in base.get("artifacts", {}).get("glossary", []):
            if isinstance(entry, dict):
                _add(entry.get("term") or entry.get("name"))

        return topics[:max_topics]
