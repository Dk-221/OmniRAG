"""
get_news_tool – Google News RSS feed, parsed with feedparser.

No API key required. Returns up to 6 recent news items for any topic,
with title, source, published time, and link. Caches for 5 minutes.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from cachetools import TTLCache

from src.tools._base import BaseTool, truncate

logger = logging.getLogger(__name__)

_CACHE: TTLCache = TTLCache(maxsize=128, ttl=300)
_RSS_URL = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
_MAX_ITEMS = 6


class GetNewsTool(BaseTool):
    """Fetch recent news articles on any topic via Google News RSS. Returns up to 6 items with title, source, published time, and link."""

    name = "get_news"
    description = (
        "Fetch the latest news headlines and articles from Google News RSS. "
        "Use for breaking news, current events, specific topics, or general top stories. "
        "Works even if no specific date or direct article URL is given."
    )
    parameters = {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "News topic, keyword, or URL (e.g. 'AI developments', 'India', or 'top stories').",
            }
        },
        "required": [],
    }
    category = "web"

    def __init__(self) -> None:
        self._last_artifact: Optional[Dict[str, Any]] = None

    def run(self, topic: str = "", **_: Any) -> str:  # type: ignore[override]
        """Fetch Google News RSS for *topic* and return formatted items."""
        self._last_artifact = None
        topic = (topic or "").strip()

        # If a URL was passed to get_news, delegate to ReadUrlTool
        if topic.startswith(("http://", "https://")):
            from src.tools.read_url_tool import ReadUrlTool
            return ReadUrlTool().run(topic)

        cache_key = f"news:{topic.lower()}"
        if cache_key in _CACHE:
            cached_text, cached_art = _CACHE[cache_key]
            self._last_artifact = cached_art
            return cached_text

        # If empty or general topic, fetch top stories RSS
        if not topic or topic.lower() in ("top", "top stories", "latest", "news", "today", "headlines", "general", "breaking", "all"):
            url = "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"
        else:
            url = _RSS_URL.format(query=quote(topic))

        try:
            import feedparser  # noqa: PLC0415
            feed = feedparser.parse(
                url,
                agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) OmniRag/1.0",
            )
        except ImportError:
            return "[Error] feedparser is not installed. Run: pip install feedparser"
        except Exception as exc:
            return f"[Error] News feed fetch failed: {exc}"

        entries = feed.entries[:_MAX_ITEMS]
        if not entries:
            return f"No recent news found for '{topic}'."

        lines = []
        news_items: List[Dict[str, str]] = []
        for i, entry in enumerate(entries, start=1):
            title = entry.get("title", "No title")
            link = entry.get("link", "")
            source = entry.get("source", {}).get("title", "Google News")
            published = entry.get("published", "")[:16]
            lines.append(
                f"[{i}] {title}\n"
                f"     Source: {source} | {published}\n"
                f"     {link}"
            )
            news_items.append({
                "title": title,
                "source": source,
                "published": published,
                "url": link,
            })

        self._last_artifact = {
            "kind": "news",
            "data": {"items": news_items},
        }

        result = "\n\n".join(lines)
        result = truncate(result)
        _CACHE[topic] = (result, self._last_artifact)
        return result
