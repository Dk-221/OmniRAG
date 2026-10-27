"""
search_papers_tool – search arXiv for academic papers via the public Atom feed API.

No API key required. Returns up to 5 results with title, authors, date,
abstract snippet, and link. Caches results for 5 minutes.
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
_CACHE: TTLCache = TTLCache(maxsize=128, ttl=300)
_USER_AGENT = "OmniRAG-Bot/1.0 (educational project)"
_API = "https://export.arxiv.org/api/query?search_query={query}&start=0&max_results=5&sortBy=submittedDate&sortOrder=descending"


class SearchPapersTool(BaseTool):
    """Search arXiv for academic research papers using the public Atom API. Returns up to 5 results with title, authors, published date, abstract snippet, and PDF link."""

    name = "search_papers"
    description = (
        "Search arXiv for academic papers on a research topic. "
        "Use for scientific questions, research queries, or finding papers on ML, physics, math, CS, etc."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Research topic or keywords to search for on arXiv.",
            }
        },
        "required": ["query"],
    }
    category = "web"

    def run(self, query: str, **_: Any) -> str:  # type: ignore[override]
        """Search arXiv for *query* and return formatted paper list."""
        query = query.strip()
        cache_key = f"arxiv:{query}"
        if cache_key in _CACHE:
            return _CACHE[cache_key]

        encoded = quote(query)
        url = _API.format(query=encoded)

        try:
            with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
                resp = client.get(url, headers={"User-Agent": _USER_AGENT})
                resp.raise_for_status()
                content = resp.text
        except Exception as exc:
            return f"[Error] arXiv search failed: {exc}"

        # Parse Atom feed
        try:
            import xml.etree.ElementTree as ET  # noqa: PLC0415, N814
            ns = {
                "atom": "http://www.w3.org/2005/Atom",
                "arxiv": "http://arxiv.org/schemas/atom",
            }
            root = ET.fromstring(content)
            entries = root.findall("atom:entry", ns)
        except Exception as exc:
            return f"[Error] Could not parse arXiv response: {exc}"

        if not entries:
            return f"No arXiv papers found for '{query}'."

        lines = []
        for i, entry in enumerate(entries[:5], start=1):
            def _text(tag: str) -> str:
                el = entry.find(tag, ns)
                return (el.text or "").strip() if el is not None else ""

            title = _text("atom:title").replace("\n", " ")
            published = _text("atom:published")[:10]  # YYYY-MM-DD
            abstract = _text("atom:summary").replace("\n", " ")[:200]
            authors = [
                (a.find("atom:name", ns).text or "").strip()
                for a in entry.findall("atom:author", ns)
                if a.find("atom:name", ns) is not None
            ]
            link_el = entry.find("atom:id", ns)
            link = (link_el.text or "").replace("abs", "pdf").strip()

            lines.append(
                f"[{i}] {title}\n"
                f"     Authors: {', '.join(authors[:3])}{'...' if len(authors) > 3 else ''}\n"
                f"     Published: {published}\n"
                f"     Abstract: {abstract}…\n"
                f"     Link: {link}"
            )

        result = "\n\n".join(lines)
        result = truncate(result)
        _CACHE[cache_key] = result
        return result
