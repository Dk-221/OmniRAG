"""
web_search_tool – live DuckDuckGo search via the `duckduckgo-search` (ddgs) package.

No API key required.
Use this tool for questions about current events, recent news, or real-time internet data.
"""

from __future__ import annotations

import logging
from typing import Any

from duckduckgo_search import DDGS

from src.tools._base import BaseTool

logger = logging.getLogger(__name__)

_MAX_RESULTS = 4
_SNIPPET_CHARS = 300


class WebSearchTool(BaseTool):
    """Perform a live DuckDuckGo web search and return top results."""

    name = "web_search"
    description = (
        "Search the web using DuckDuckGo for current, real-time information and recent news. "
        "Returns the top results with title, URL, and snippets."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to look up on the web.",
            }
        },
        "required": ["query"],
    }
    category = "web"

    def run(self, query: str, **_: Any) -> str:  # type: ignore[override]
        """Execute a DuckDuckGo text search and return formatted results."""
        logger.info("Web search: %s", query)
        q_strip = (query or "").strip()
        if q_strip.startswith(("http://", "https://")):
            try:
                from src.tools.read_url_tool import ReadUrlTool
                logger.info("web_search received direct URL; delegating to ReadUrlTool: %s", q_strip)
                return ReadUrlTool().run(q_strip)
            except Exception as exc:
                logger.warning("Delegation to ReadUrlTool failed: %s", exc)

        results = []
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=_MAX_RESULTS):
                    results.append(r)
        except Exception as exc:
            logger.warning("DuckDuckGo search failed: %s", exc)
            return f"Web search failed: {exc}"

        if not results:
            return "No web search results found."

        lines = []
        for i, r in enumerate(results, start=1):
            snippet = (r.get("body") or "")[:_SNIPPET_CHARS]
            lines.append(
                f"[{i}] {r.get('title', 'No title')}\n"
                f"     URL: {r.get('href', '')}\n"
                f"     {snippet}"
            )
        return "\n\n".join(lines)
