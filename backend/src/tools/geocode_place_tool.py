"""
geocode_place_tool – OpenStreetMap Nominatim geocoding.

Converts a place name/address to coordinates and structured location data.
Respects Nominatim's rate limit of 1 request/second using an asyncio Lock.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import httpx
from cachetools import TTLCache

from src.tools._base import BaseTool, truncate

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0
_CACHE: TTLCache = TTLCache(maxsize=256, ttl=300)
_USER_AGENT = "OmniRAG-Bot/1.0 (educational project; contact: admin@example.com)"
_API = "https://nominatim.openstreetmap.org/search"
_LAST_CALL_LOCK = threading.Lock()
_LAST_CALL_TIME: float = 0.0
_MIN_INTERVAL = 1.1  # seconds between calls (Nominatim policy: max 1 req/sec)


def _rate_limited_get(url: str, params: dict) -> httpx.Response:
    """Enforce 1 request/second to Nominatim."""
    global _LAST_CALL_TIME
    with _LAST_CALL_LOCK:
        now = time.monotonic()
        elapsed = now - _LAST_CALL_TIME
        if elapsed < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - elapsed)
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(url, params=params, headers={"User-Agent": _USER_AGENT})
        _LAST_CALL_TIME = time.monotonic()
    return resp


class GeocodePlaceTool(BaseTool):
    """Convert a place name or address to GPS coordinates using OpenStreetMap Nominatim. Returns lat/lon, display name, country, and place type."""

    name = "geocode_place"
    description = (
        "Look up the GPS coordinates (latitude/longitude) and structured location details "
        "for any address, city, landmark, or place name using OpenStreetMap Nominatim."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Place name, address, or landmark to geocode (e.g. 'Eiffel Tower', 'Mumbai, India').",
            }
        },
        "required": ["query"],
    }
    category = "utility"

    def run(self, query: str, **_: Any) -> str:  # type: ignore[override]
        """Geocode *query* using Nominatim."""
        query = query.strip()
        if query in _CACHE:
            return _CACHE[query]

        try:
            resp = _rate_limited_get(
                _API,
                {
                    "q": query,
                    "format": "json",
                    "limit": 3,
                    "addressdetails": 1,
                },
            )
            resp.raise_for_status()
            results = resp.json()
        except Exception as exc:
            return f"[Error] Geocoding failed: {exc}"

        if not results:
            return f"No location found for '{query}'. Try a more specific place name."

        lines = []
        for i, r in enumerate(results[:3], start=1):
            addr = r.get("address", {})
            country = addr.get("country", "")
            place_type = r.get("type", r.get("class", ""))
            display = r.get("display_name", "")
            lat = r.get("lat", "?")
            lon = r.get("lon", "?")
            lines.append(
                f"[{i}] {display}\n"
                f"     Lat: {lat}, Lon: {lon}\n"
                f"     Type: {place_type} | Country: {country}"
            )

        result = "\n\n".join(lines)
        result = truncate(result)
        _CACHE[query] = result
        return result
