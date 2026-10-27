"""
wikipedia_lookup_tool – Wikipedia REST API summary endpoint.

Uses the Wikipedia Summary API (no key). Caches for 5 minutes.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import httpx
from cachetools import TTLCache

from src.tools._base import BaseTool, truncate

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0
_CACHE: TTLCache = TTLCache(maxsize=256, ttl=300)
_USER_AGENT = "OmniRAG-Bot/1.0 (educational project)"
_API = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"


class WikipediaLookupTool(BaseTool):
    """Look up a concise summary of any topic from Wikipedia's REST API. Returns the extract, page URL, and thumbnail description."""

    name = "wikipedia_lookup"
    description = (
        "Look up a factual summary of a topic, person, place, or concept from Wikipedia. "
        "Best for encyclopaedic background information; not for current news or live data."
    )
    parameters = {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "The topic or entity to look up (e.g. 'Quantum computing', 'Elon Musk').",
            }
        },
        "required": ["topic"],
    }
    category = "web"

    def run(self, topic: str, **_: Any) -> str:  # type: ignore[override]
        """Fetch Wikipedia summary for *topic*."""
        topic = topic.strip()
        if topic in _CACHE:
            return _CACHE[topic]

        encoded = quote(topic.replace(" ", "_"), safe="")
        url = _API.format(encoded)

        try:
            with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
                resp = client.get(url, headers={"User-Agent": _USER_AGENT})
                if resp.status_code == 404:
                    # Try search redirect
                    search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={quote(topic)}&format=json&srlimit=1"
                    sr = client.get(search_url, headers={"User-Agent": _USER_AGENT})
                    sr.raise_for_status()
                    hits = sr.json().get("query", {}).get("search", [])
                    if not hits:
                        return f"No Wikipedia article found for '{topic}'."
                    best = hits[0]["title"]
                    encoded2 = quote(best.replace(" ", "_"), safe="")
                    resp = client.get(_API.format(encoded2), headers={"User-Agent": _USER_AGENT})
                resp.raise_for_status()
        except httpx.TimeoutException:
            return "[Error] Wikipedia request timed out."
        except Exception as exc:
            return f"[Error] Wikipedia lookup failed: {exc}"

        data = resp.json()
        title = data.get("title", topic)
        extract = data.get("extract", "")
        page_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")

        result = f"**{title}**\n\n{extract}"
        if page_url:
            result += f"\n\nSource: {page_url}"

        result = truncate(result)
        _CACHE[topic] = result
        return result
