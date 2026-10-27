"""
air_quality_tool – city air quality via Open-Meteo Air Quality API.

Geocodes the city using Open-Meteo's geocoding API, then fetches
current US AQI, PM2.5, PM10, and provides a health advisory note.
No API key required.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from cachetools import TTLCache

from src.tools._base import BaseTool, truncate

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0
_CACHE: TTLCache = TTLCache(maxsize=128, ttl=300)
_GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
_AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


def _aqi_label(aqi: float | None) -> str:
    """Convert US AQI value to health category."""
    if aqi is None:
        return "Unknown"
    if aqi <= 50:
        return "Good"
    if aqi <= 100:
        return "Moderate"
    if aqi <= 150:
        return "Unhealthy for Sensitive Groups"
    if aqi <= 200:
        return "Unhealthy"
    if aqi <= 300:
        return "Very Unhealthy"
    return "Hazardous"


def _health_note(aqi: float | None) -> str:
    if aqi is None:
        return "Data unavailable."
    if aqi <= 50:
        return "Air quality is satisfactory and poses little or no risk."
    if aqi <= 100:
        return "Acceptable, but sensitive individuals may experience discomfort."
    if aqi <= 150:
        return "Sensitive groups (elderly, children, those with respiratory issues) should limit outdoor activity."
    if aqi <= 200:
        return "Everyone may experience health effects; sensitive groups should avoid outdoor exertion."
    if aqi <= 300:
        return "Health alert: everyone may experience serious health effects. Avoid outdoor activity."
    return "Emergency conditions: entire population is likely to be affected. Stay indoors."


class AirQualityTool(BaseTool):
    """Get current air quality index (US AQI), PM2.5, and PM10 for any city using Open-Meteo's free API. Includes a plain-language health advisory."""

    name = "air_quality"
    description = (
        "Check the current air quality and pollution levels for any city worldwide. "
        "Returns US AQI, PM2.5, PM10 concentration, and a health advisory note."
    )
    parameters = {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "City name to check air quality for (e.g. 'Delhi', 'Beijing', 'London').",
            }
        },
        "required": ["city"],
    }
    category = "utility"

    def run(self, city: str, **_: Any) -> str:  # type: ignore[override]
        """Fetch air quality for *city*."""
        city = city.strip()
        if city in _CACHE:
            return _CACHE[city]

        # Geocode
        try:
            with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
                geo = client.get(
                    _GEO_URL,
                    params={"name": city, "count": 1, "language": "en", "format": "json"},
                )
                geo.raise_for_status()
                geo_data = geo.json()
        except Exception as exc:
            return f"[Error] Geocoding failed: {exc}"

        results = geo_data.get("results", [])
        if not results:
            return f"Could not find city '{city}'. Check the spelling."

        loc = results[0]
        lat, lon = loc["latitude"], loc["longitude"]
        display = f"{loc['name']}, {loc.get('country', '')}"

        # Air quality
        try:
            with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
                aq = client.get(
                    _AQ_URL,
                    params={
                        "latitude": lat,
                        "longitude": lon,
                        "current": "us_aqi,pm2_5,pm10,carbon_monoxide,nitrogen_dioxide,ozone",
                        "timezone": "auto",
                    },
                )
                aq.raise_for_status()
                aq_data = aq.json()
        except Exception as exc:
            return f"[Error] Air quality fetch failed: {exc}"

        cur = aq_data.get("current", {})
        aqi = cur.get("us_aqi")
        pm25 = cur.get("pm2_5")
        pm10 = cur.get("pm10")
        co = cur.get("carbon_monoxide")
        no2 = cur.get("nitrogen_dioxide")
        ozone = cur.get("ozone")

        lines = [
            f"Air Quality: {display}",
            f"US AQI: {aqi} — {_aqi_label(aqi)}",
            f"PM2.5: {pm25} µg/m³" if pm25 is not None else "PM2.5: N/A",
            f"PM10: {pm10} µg/m³" if pm10 is not None else "PM10: N/A",
            f"CO: {co} µg/m³" if co is not None else "",
            f"NO₂: {no2} µg/m³" if no2 is not None else "",
            f"Ozone: {ozone} µg/m³" if ozone is not None else "",
            f"\n💡 Health Advisory: {_health_note(aqi)}",
        ]

        result = "\n".join(l for l in lines if l)
        result = truncate(result)
        _CACHE[city] = result
        return result
