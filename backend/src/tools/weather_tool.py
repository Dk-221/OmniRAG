"""
weather_tool – current conditions + 3-day forecast via Open-Meteo (no API key).

Uses Open-Meteo geocoding to resolve city to coordinates, then fetches current
conditions and daily forecast. Returns a text summary and a weather artifact.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from src.tools._base import BaseTool

logger = logging.getLogger(__name__)

_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_TIMEOUT = 10.0  # seconds

# WMO weather interpretation codes → human label
_WMO_CODES: dict[int, str] = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Icy fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    80: "Slight showers", 81: "Moderate showers", 82: "Heavy showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}


def _wmo(code: int) -> str:
    return _WMO_CODES.get(code, f"Code {code}")


class WeatherTool(BaseTool):
    """Fetch current weather and 3-day forecast for any city worldwide."""

    name = "get_weather"
    description = (
        "Get current weather and 3-day forecast for any city using Open-Meteo. "
        "Returns temperature, conditions, humidity, wind, and daily forecast."
    )
    parameters = {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "The city name, e.g. 'London', 'Tokyo', 'Mumbai', 'New York'.",
            }
        },
        "required": ["city"],
    }
    category = "utility"

    def __init__(self) -> None:
        self._last_artifact: Optional[Dict[str, Any]] = None

    def run(self, city: str, **_: Any) -> str:  # type: ignore[override]
        """Geocode *city* and return current + 3-day weather."""
        self._last_artifact = None
        city = city.strip()
        logger.info("Weather lookup for: %s", city)

        headers = {"User-Agent": "OmniRag/1.0 (free agent)"}

        # ── 1. Geocoding ──────────────────────────────────────────────────
        with httpx.Client(timeout=_TIMEOUT, headers=headers, follow_redirects=True) as client:
            geo_resp = client.get(
                _GEOCODE_URL,
                params={"name": city, "count": 1, "language": "en", "format": "json"},
            )
            geo_resp.raise_for_status()
            geo_data = geo_resp.json()

            if not geo_data.get("results"):
                return f"Could not find the city '{city}'. Please check the spelling."

            loc = geo_data["results"][0]
            lat = loc["latitude"]
            lon = loc["longitude"]
            display_name = f"{loc['name']}, {loc.get('country', '')}"

            # ── 2. Forecast ───────────────────────────────────────────────────
            fc_resp = client.get(
                _FORECAST_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": (
                        "temperature_2m,relative_humidity_2m,apparent_temperature,"
                        "precipitation,weather_code,wind_speed_10m"
                    ),
                    "daily": (
                        "weather_code,temperature_2m_max,temperature_2m_min,"
                        "precipitation_sum"
                    ),
                    "forecast_days": 4,
                    "timezone": "auto",
                },
            )
            fc_resp.raise_for_status()
            fc = fc_resp.json()

        cur = fc.get("current", {})
        daily = fc.get("daily", {})

        temp = cur.get("temperature_2m")
        feels = cur.get("apparent_temperature")
        humidity = cur.get("relative_humidity_2m")
        precip = cur.get("precipitation", 0)
        wind = cur.get("wind_speed_10m")
        wcode = cur.get("weather_code", 0)
        condition_str = _wmo(wcode)

        dates = daily.get("time", [])
        max_temps = daily.get("temperature_2m_max", [])
        min_temps = daily.get("temperature_2m_min", [])
        day_codes = daily.get("weather_code", [])

        forecast_list: List[Dict[str, Any]] = []
        for i in range(1, min(4, len(dates))):
            d_label = dates[i] if i < len(dates) else "?"
            hi = max_temps[i] if i < len(max_temps) else None
            lo = min_temps[i] if i < len(min_temps) else None
            dc = day_codes[i] if i < len(day_codes) else 0
            forecast_list.append({
                "day": d_label,
                "min": lo,
                "max": hi,
                "condition": _wmo(dc),
            })

        # Emit weather artifact: {city, current_temp, condition, forecast: [{day, min, max, condition}]}
        self._last_artifact = {
            "kind": "weather",
            "data": {
                "city": display_name,
                "current_temp": temp,
                "condition": condition_str,
                "forecast": forecast_list,
            },
        }

        lines = [
            f"Weather for {display_name}: {temp}°C, {condition_str} (Feels like {feels}°C)",
            f"Humidity: {humidity}%, Wind: {wind} km/h, Precip: {precip} mm",
            "Forecast:",
        ]
        for f in forecast_list:
            lines.append(f"  {f['day']}: {f['condition']}, High {f['max']}°C / Low {f['min']}°C")

        return "\n".join(lines)
