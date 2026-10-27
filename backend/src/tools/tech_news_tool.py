"""
tech_news_tool – Hacker News top stories and search via the Algolia API.

No API key required. Returns top HN stories or searches by query,
including points and link. Caches for 5 minutes.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from urllib.parse import quote

import httpx
from cachetools import TTLCache

from src.tools._base import BaseTool, truncate

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0
_CACHE: TTLCache = TTLCache(maxsize=128, ttl=300)
_USER_AGENT = "OmniRAG-Bot/1.0 (educational project)"
_HN_SEARCH = "https://hn.algolia.com/api/v1/search?query={query}&tags=story&hitsPerPage=6"
_HN_TOP = "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=6"


class TechNewsTool(BaseTool):
    """Fetch top tech stories or search Hacker News via the Algolia API. Returns story titles, points, comment counts, and links."""

    name = "tech_news"
    description = (
        "Search Hacker News for tech industry news, startup stories, and developer community discussions. "
        "Leave query empty to get today's front-page stories."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query for HN stories. Leave empty for top front-page stories.",
            }
        },
        "required": [],
    }
    category = "web"

    def run(self, query: Optional[str] = None, **_: Any) -> str:  # type: ignore[override]
        """Fetch HN stories matching *query*, or front-page if empty."""
        q = (query or "").strip()
        cache_key = f"hn:{q}"
        if cache_key in _CACHE:
            return _CACHE[cache_key]

        url = _HN_SEARCH.format(query=quote(q)) if q else _HN_TOP

        try:
            with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
                resp = client.get(url, headers={"User-Agent": _USER_AGENT})
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            return f"[Error] Hacker News search failed: {exc}"

        hits = data.get("hits", [])
        if not hits:
            label = f"'{q}'" if q else "top stories"
            return f"No Hacker News stories found for {label}."

        lines = []
        for i, h in enumerate(hits[:6], start=1):
            title = h.get("title", "No title")
            url_ = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID', '')}"
            points = h.get("points") or 0
            comments = h.get("num_comments") or 0
            lines.append(
                f"[{i}] {title}\n"
                f"     Points: {points} | Comments: {comments}\n"
                f"     {url_}"
            )

        result = "\n\n".join(lines)
        result = truncate(result)
        _CACHE[cache_key] = result
        return result
