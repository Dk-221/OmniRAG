"""
read_url_tool – fetch a webpage and extract its main text content.

Uses httpx for fetching and trafilatura for main-content extraction.
Blocks SSRF: localhost, private IP ranges, and non-http(s) schemes.
Provides native Google News feed conversion and rich meta-fallback.
Caches responses for 5 minutes.
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
from typing import Any
from urllib.parse import urlparse

import httpx
from cachetools import TTLCache

from src.tools._base import BaseTool, truncate

logger = logging.getLogger(__name__)

_TIMEOUT = 12.0
_CACHE: TTLCache = TTLCache(maxsize=128, ttl=300)  # 5-min TTL
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
_MODEL_MAX = 3500
_FULL_MAX = 10000


def _is_private_or_localhost(hostname: str) -> bool:
    """Return True if hostname resolves to a private/loopback address."""
    try:
        ip_str = socket.gethostbyname(hostname)
        addr = ipaddress.ip_address(ip_str)
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except Exception:
        return True  # err on the side of caution


def _check_url(url: str) -> str | None:
    """Return an error string if the URL is blocked, else None."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return f"Blocked scheme '{parsed.scheme}'. Only http and https are allowed."
    hostname = parsed.hostname or ""
    if not hostname:
        return "Invalid URL: no hostname."
    if _is_private_or_localhost(hostname):
        return f"Blocked: '{hostname}' resolves to a private or loopback address (SSRF protection)."
    return None


def _handle_google_news(url: str) -> str | None:
    """Special handling for Google News pages to retrieve clean, live news articles via RSS."""
    parsed = urlparse(url)
    if "news.google.com" not in parsed.netloc.lower():
        return None

    qs = parsed.query
    path = parsed.path.strip("/")

    if "topics" in path:
        rss_url = f"https://news.google.com/rss/{path}" + (f"?{qs}" if qs else "")
    elif "search" in path and qs:
        rss_url = f"https://news.google.com/rss/search?{qs}"
    elif qs:
        rss_url = f"https://news.google.com/rss?{qs}"
    else:
        rss_url = "https://news.google.com/rss"

    try:
        import feedparser  # noqa: PLC0415
        feed = feedparser.parse(
            rss_url,
            agent=_USER_AGENT,
        )
        if feed.entries:
            feed_title = feed.feed.get("title", "Google News Top Stories")
            lines = [f"=== Google News Live Feed: {feed_title} ===\n"]
            for i, entry in enumerate(feed.entries[:8], start=1):
                entry_title = entry.get("title", "No title")
                src = entry.get("source", {}).get("title", "News Source")
                pub = entry.get("published", "")
                link = entry.get("link", "")
                raw_summary = entry.get("summary", "")
                clean_summary = re.sub(r"<[^>]+>", " ", raw_summary).strip()
                clean_summary = re.sub(r"\s+", " ", clean_summary)

                lines.append(f"[{i}] {entry_title}")
                lines.append(f"    Source: {src} | Date: {pub}")
                if clean_summary and clean_summary != entry_title:
                    lines.append(f"    Summary: {clean_summary[:280]}")
                if link:
                    lines.append(f"    URL: {link}")
                lines.append("")
            return "\n".join(lines).strip()
    except Exception as exc:
        logger.warning("Failed to parse Google News RSS: %s", exc)

    return None


def _extract_meta_fallback(html: str) -> str:
    """Extract page title, meta description, og:description, and readable paragraph text."""
    parts = []
    # Title
    t_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if t_match:
        title = re.sub(r"\s+", " ", t_match.group(1)).strip()
        if title:
            parts.append(f"Title: {title}")

    # Meta descriptions
    d_match = re.search(r'<meta[^>]+(?:name|property)=["\'](?:og:)?description["\'][^>]+content=["\'](.*?)["\']', html, re.IGNORECASE | re.DOTALL)
    if d_match:
        desc = re.sub(r"\s+", " ", d_match.group(1)).strip()
        if desc:
            parts.append(f"Description: {desc}")

    # Headings & Paragraphs
    body_blocks = re.findall(r"<(?:h[1-4]|p|article)[^>]*>(.*?)</(?:h[1-4]|p|article)>", html, re.IGNORECASE | re.DOTALL)
    cleaned_blocks = []
    for b in body_blocks:
        clean = re.sub(r"<[^>]+>", " ", b).strip()
        clean = re.sub(r"\s+", " ", clean)
        if len(clean) > 25 and clean not in cleaned_blocks:
            cleaned_blocks.append(clean)

    if cleaned_blocks:
        parts.append("\n" + "\n\n".join(cleaned_blocks[:15]))

    return "\n\n".join(parts).strip()


class ReadUrlTool(BaseTool):
    """Fetch a public webpage and extract its main text content. Automatically parses Google News feeds and handles dynamic news sites."""

    name = "read_url"
    description = (
        "Fetch and extract readable text from a public webpage URL or news portal. "
        "Use whenever the user provides a specific URL (e.g. Google News, articles, blogs, websites) "
        "or when full page content is required. Works even for news homepages and aggregation links."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The full public URL (http or https) to fetch and read.",
            }
        },
        "required": ["url"],
    }
    category = "web"

    def run(self, url: str, **_: Any) -> str:  # type: ignore[override]
        """Fetch *url* and return extracted text."""
        url = url.strip()

        # SSRF check
        block_reason = _check_url(url)
        if block_reason:
            return f"[Error] {block_reason}"

        # Cache hit
        if url in _CACHE:
            logger.debug("read_url cache hit: %s", url)
            return _CACHE[url]

        # 1. Google News special handling (RSS feed conversion)
        gnews_text = _handle_google_news(url)
        if gnews_text:
            result = truncate(gnews_text, _MODEL_MAX)
            _CACHE[url] = result
            return result

        # 2. General HTTP Fetch
        try:
            with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
                resp = client.get(url, headers={"User-Agent": _USER_AGENT})
                resp.raise_for_status()
                html = resp.text
        except httpx.TimeoutException:
            return "[Error] Request timed out (12s)."
        except httpx.HTTPStatusError as exc:
            return f"[Error] HTTP {exc.response.status_code}: {exc.response.reason_phrase}"
        except Exception as exc:
            return f"[Error] Could not fetch URL: {exc}"

        # 3. Extract main text via Trafilatura
        text = ""
        try:
            import trafilatura  # noqa: PLC0415
            text = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                no_fallback=False,
            ) or ""
        except Exception:
            pass

        # 4. Fallback if extraction is too short or empty
        if len(text.strip()) < 150:
            fallback = _extract_meta_fallback(html)
            if len(fallback.strip()) > len(text.strip()):
                text = fallback

        if not text.strip():
            return "[Error] Could not extract readable text from this URL. The page may require JavaScript or authentication."

        full_text = text[:_FULL_MAX]
        result = truncate(full_text, _MODEL_MAX)
        _CACHE[url] = result
        return result
