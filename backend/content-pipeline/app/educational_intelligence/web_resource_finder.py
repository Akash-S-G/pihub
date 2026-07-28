from __future__ import annotations

"""Multi-source web resource finder for the enriched content agent.

Searches the open web (not only YouTube) for related videos, explanatory
articles, and real-world reference material for a given topic. Designed to
degrade gracefully:

    * YouTube Data API v3   -> used when ``YOUTUBE_API_KEY`` is configured.
    * YouTube HTML search   -> keyless fallback for videos (best-effort scrape).
    * DuckDuckGo HTML        -> keyless general web search (articles/pages).
    * Wikipedia REST API     -> authoritative concept explanation.

Every network call is wrapped so that a timeout / offline environment never
breaks artifact generation — the finder simply returns fewer resources.
"""

import json
import logging
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

import httpx

from shared.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class WebResource:
    title: str
    url: str
    resource_type: str  # "video" | "article" | "reference" | "simulation"
    source: str
    description: str = ""
    thumbnail: str = ""
    language: str = "en"
    relevance: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "resource_type": self.resource_type,
            "source": self.source,
            "description": self.description,
            "thumbnail": self.thumbnail,
            "language": self.language,
            "relevance": round(self.relevance, 3),
        }


@dataclass
class TopicResources:
    topic: str
    language: str = "en"
    videos: list[WebResource] = field(default_factory=list)
    articles: list[WebResource] = field(default_factory=list)
    references: list[WebResource] = field(default_factory=list)
    simulations: list[WebResource] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "language": self.language,
            "videos": [v.to_dict() for v in self.videos],
            "articles": [a.to_dict() for a in self.articles],
            "references": [r.to_dict() for r in self.references],
            "simulations": [s.to_dict() for s in self.simulations],
        }


# Language name used to bias search queries towards the right localized content.
_LANG_QUERY_HINT = {
    "en": "",
    "kn": "Kannada",
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "ml": "Malayalam",
}

# Wikipedia language subdomains we support.
_WIKI_LANG = {"en", "kn", "hi", "ta", "te", "ml"}


class WebResourceFinder:
    """Find related videos / articles / references for a topic across the web."""

    def __init__(
        self,
        timeout: float | None = None,
        max_per_topic: int | None = None,
        youtube_api_key: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        settings = get_settings()
        self.timeout = timeout if timeout is not None else settings.web_enrichment_timeout_seconds
        self.max_per_topic = max_per_topic or settings.web_enrichment_max_per_topic
        self.youtube_api_key = (
            youtube_api_key if youtube_api_key is not None else settings.youtube_api_key
        )
        self.user_agent = user_agent or settings.enrichment_user_agent
        self.enabled = settings.enable_web_enrichment
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={"User-Agent": self.user_agent},
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _query(self, topic: str, language: str, suffix: str = "") -> str:
        hint = _LANG_QUERY_HINT.get(language, "")
        parts = [topic]
        if hint:
            parts.append(hint)
        if suffix:
            parts.append(suffix)
        return " ".join(p for p in parts if p).strip()

    async def find(self, topic: str, language: str = "en", subject: str | None = None) -> TopicResources:
        """Aggregate videos, articles, and references for one topic."""
        result = TopicResources(topic=topic, language=language)
        if not self.enabled or not topic.strip():
            return result

        videos = await self._find_videos(topic, language, subject)
        articles = await self._find_articles(topic, language, subject)
        reference = await self._find_wikipedia(topic, language)
        simulations = await self._find_simulations(topic, language, subject)

        result.videos = videos[: self.max_per_topic]
        result.articles = articles[: self.max_per_topic]
        if reference:
            result.references = [reference]
        result.simulations = simulations[: self.max_per_topic]
        return result

    async def find_multi(
        self, topic: str, languages: list[str], subject: str | None = None
    ) -> TopicResources:
        """Fetch resources for several languages and merge them into one block.

        Used to gather Kannada AND English content for the same topic so the
        offline app can offer both. Each resource keeps its own ``language`` tag;
        duplicates (same URL) are removed, preferring the earlier language.
        """
        merged = TopicResources(topic=topic, language=",".join(languages))
        seen: set[str] = set()

        def _extend(dst: list[WebResource], src: list[WebResource]) -> None:
            for r in src:
                key = r.url or r.title
                if key and key not in seen:
                    seen.add(key)
                    dst.append(r)

        for lang in languages:
            part = await self.find(topic, language=lang, subject=subject)
            _extend(merged.videos, part.videos)
            _extend(merged.articles, part.articles)
            _extend(merged.references, part.references)
            _extend(merged.simulations, part.simulations)
        return merged

    # ------------------------------------------------------------------ videos
    async def _find_videos(self, topic: str, language: str, subject: str | None) -> list[WebResource]:
        suffix = "explanation experiment" if subject else "explained"
        query = self._query(topic, language, suffix)
        if self.youtube_api_key:
            api_results = await self._youtube_api_search(query, language)
            if api_results:
                return api_results
        return await self._youtube_html_search(query, language)

    async def _youtube_api_search(self, query: str, language: str) -> list[WebResource]:
        try:
            client = await self._get_client()
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "maxResults": self.max_per_topic,
                    "safeSearch": "strict",
                    "videoEmbeddable": "true",
                    "relevanceLanguage": language,
                    "key": self.youtube_api_key,
                },
            )
            if not resp.is_success:
                logger.warning("YouTube API returned %s", resp.status_code)
                return []
            items = resp.json().get("items", [])
            resources: list[WebResource] = []
            for it in items:
                vid = it.get("id", {}).get("videoId")
                sn = it.get("snippet", {})
                if not vid:
                    continue
                thumbs = sn.get("thumbnails", {})
                resources.append(
                    WebResource(
                        title=sn.get("title", "Untitled"),
                        url=f"https://www.youtube.com/watch?v={vid}",
                        resource_type="video",
                        source=sn.get("channelTitle", "YouTube"),
                        description=sn.get("description", "")[:300],
                        thumbnail=(thumbs.get("medium") or thumbs.get("default") or {}).get("url", ""),
                        language=language,
                        relevance=0.8,
                    )
                )
            return resources
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            logger.warning("YouTube API search failed: %s", str(exc)[:200])
            return []

    async def _youtube_html_search(self, query: str, language: str) -> list[WebResource]:
        """Keyless best-effort YouTube search via the results page JSON blob."""
        try:
            client = await self._get_client()
            resp = await client.get(
                "https://www.youtube.com/results",
                params={"search_query": query, "sp": "EgIQAQ%3D%3D"},  # sp filters to videos
            )
            if not resp.is_success:
                return []
            html = resp.text
            # video ids appear as "videoId":"XXXXXXXXXXX"
            seen: set[str] = set()
            resources: list[WebResource] = []
            for m in re.finditer(r'"videoId":"([\w-]{11})"', html):
                vid = m.group(1)
                if vid in seen:
                    continue
                seen.add(vid)
                title = self._extract_yt_title(html, vid)
                resources.append(
                    WebResource(
                        title=title or query,
                        url=f"https://www.youtube.com/watch?v={vid}",
                        resource_type="video",
                        source="YouTube",
                        thumbnail=f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg",
                        language=language,
                        relevance=0.65,
                    )
                )
                if len(resources) >= self.max_per_topic:
                    break
            return resources
        except httpx.HTTPError as exc:
            logger.warning("YouTube HTML search failed: %s", str(exc)[:200])
            return []

    @staticmethod
    def _extract_yt_title(html: str, vid: str) -> str:
        # Best-effort: find the title near the videoId occurrence.
        idx = html.find(f'"videoId":"{vid}"')
        if idx == -1:
            return ""
        window = html[idx : idx + 2000]
        m = re.search(r'"title":\{"runs":\[\{"text":"([^"]+)"', window)
        if m:
            try:
                return json.loads(f'"{m.group(1)}"')
            except json.JSONDecodeError:
                return m.group(1)
        return ""

    # ---------------------------------------------------------------- articles
    async def _find_articles(self, topic: str, language: str, subject: str | None) -> list[WebResource]:
        suffix = "real world examples applications"
        query = self._query(topic, language, suffix)
        return await self._duckduckgo_search(query, language, resource_type="article", relevance=0.6)

    # ------------------------------------------------------------- simulations
    # Domains that host interactive simulations / virtual labs. Results from
    # these are re-classified as "simulation". This searches the OPEN WEB for
    # simulations and is independent of the local PhET catalog / EnrichmentRouter.
    _SIM_DOMAINS = (
        "phet.colorado.edu",
        "olabs.edu.in",
        "geogebra.org",
        "javalab.org",
        "physicsclassroom.com",
        "explorelearning.com",
        "labxchange.org",
        "molecularworkbench",
        "simulations.",
        "ophysics.com",
        "thephysicsaviary.com",
    )

    async def _find_simulations(self, topic: str, language: str, subject: str | None) -> list[WebResource]:
        query = self._query(topic, language, "interactive simulation virtual lab")
        hits = await self._duckduckgo_search(
            query, language, resource_type="simulation", relevance=0.6
        )
        # Prefer results from known simulation providers; keep others as fallback.
        preferred: list[WebResource] = []
        fallback: list[WebResource] = []
        for h in hits:
            domain = h.url.lower()
            if any(d in domain for d in self._SIM_DOMAINS):
                h.relevance = max(h.relevance, 0.8)
                preferred.append(h)
            else:
                fallback.append(h)
        return preferred + fallback

    async def _duckduckgo_search(
        self,
        query: str,
        language: str,
        resource_type: str = "article",
        relevance: float = 0.6,
    ) -> list[WebResource]:
        """Keyless DuckDuckGo HTML endpoint scrape."""
        try:
            from bs4 import BeautifulSoup  # local import; heavy-ish

            client = await self._get_client()
            resp = await client.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query, "kl": f"{language}-{language}" if language != "en" else "us-en"},
            )
            if not resp.is_success:
                return []
            soup = BeautifulSoup(resp.text, "lxml")
            resources: list[WebResource] = []
            for res in soup.select("div.result")[: self.max_per_topic * 3]:
                a = res.select_one("a.result__a")
                if not a:
                    continue
                href = a.get("href", "")
                url = self._unwrap_ddg(href)
                if not url:
                    continue
                snippet_el = res.select_one(".result__snippet")
                resources.append(
                    WebResource(
                        title=a.get_text(strip=True) or query,
                        url=url,
                        resource_type=resource_type,
                        source=self._domain(url),
                        description=snippet_el.get_text(strip=True)[:300] if snippet_el else "",
                        language=language,
                        relevance=relevance,
                    )
                )
                if len(resources) >= self.max_per_topic:
                    break
            return resources
        except (httpx.HTTPError, Exception) as exc:  # noqa: BLE001 - never break generation
            logger.warning("DuckDuckGo search failed: %s", str(exc)[:200])
            return []

    @staticmethod
    def _unwrap_ddg(href: str) -> str:
        if not href:
            return ""
        if href.startswith("//"):
            href = "https:" + href
        parsed = urllib.parse.urlparse(href)
        if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
            qs = urllib.parse.parse_qs(parsed.query)
            uddg = qs.get("uddg", [])
            if uddg:
                return urllib.parse.unquote(uddg[0])
        if parsed.scheme in ("http", "https"):
            return href
        return ""

    @staticmethod
    def _domain(url: str) -> str:
        try:
            netloc = urllib.parse.urlparse(url).netloc
            return netloc.replace("www.", "") or "web"
        except ValueError:
            return "web"

    # --------------------------------------------------------------- wikipedia
    async def _find_wikipedia(self, topic: str, language: str) -> WebResource | None:
        wiki_lang = language if language in _WIKI_LANG else "en"
        try:
            client = await self._get_client()
            resp = await client.get(
                f"https://{wiki_lang}.wikipedia.org/api/rest_v1/page/summary/"
                + urllib.parse.quote(topic),
            )
            if resp.status_code == 404 and wiki_lang != "en":
                # Fall back to English encyclopedia entry.
                resp = await client.get(
                    "https://en.wikipedia.org/api/rest_v1/page/summary/"
                    + urllib.parse.quote(topic),
                )
                wiki_lang = "en"
            if not resp.is_success:
                return None
            data = resp.json()
            extract = data.get("extract", "")
            if not extract:
                return None
            page_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
            return WebResource(
                title=data.get("title", topic),
                url=page_url or f"https://{wiki_lang}.wikipedia.org/wiki/{urllib.parse.quote(topic)}",
                resource_type="reference",
                source="Wikipedia",
                description=extract[:500],
                thumbnail=data.get("thumbnail", {}).get("source", ""),
                language=wiki_lang,
                relevance=0.7,
            )
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            logger.warning("Wikipedia lookup failed: %s", str(exc)[:200])
            return None
