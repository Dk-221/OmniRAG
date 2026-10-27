"""
make_chart_tool – validate chart specs and return a chart artifact.

No image is generated. The tool validates the input and returns a structured
chart artifact dict that the frontend renders.
Supported types: bar, line, pie, area.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.tools._base import BaseTool

logger = logging.getLogger(__name__)

_VALID_TYPES = {"bar", "line", "pie", "area", "candle", "candlestick"}


class MakeChartTool(BaseTool):
    """Create a structured chart artifact (bar/line/pie/area) from data. Returns a chart spec for the frontend to render — no image is generated."""

    name = "make_chart"
    description = (
        "Generate a chart artifact from structured data. "
        "Supported chart_type values: bar, line, pie, area. "
        "Returns a {type:chart} artifact with title, labels, and data series."
    )
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Chart title."},
            "chart_type": {
                "type": "string",
                "enum": ["bar", "line", "pie", "area"],
                "description": "Type of chart: bar, line, pie, or area.",
            },
            "labels": {
                "type": "array",
                "items": {"type": "string"},
                "description": "X-axis labels or pie slice names.",
            },
            "series": {
                "type": "array",
                "description": "Data series. Each item has 'name' (str) and 'data' (list of numbers).",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "data": {"type": "array", "items": {"type": "number"}},
                    },
                    "required": ["name", "data"],
                },
            },
        },
        "required": ["title", "chart_type", "labels", "series"],
    }
    category = "data"

    def run(  # type: ignore[override]
        self,
        title: str,
        chart_type: str,
        labels: List[str],
        series: List[Dict[str, Any]],
        **_: Any,
    ) -> str:
        """Validate chart spec and return a summary (artifact is emitted by agent)."""
        chart_type = chart_type.lower().strip()
        if chart_type not in _VALID_TYPES:
            return (
                f"[Error] Invalid chart_type '{chart_type}'. "
                f"Choose from: {sorted(_VALID_TYPES)}"
            )
        if not labels:
            return "[Error] 'labels' must not be empty."
        if not series:
            return "[Error] 'series' must contain at least one item."

        # Support flat array of numbers e.g. series=[100, 200, 300]
        if isinstance(series, list) and series and not isinstance(series[0], dict):
            series = [{"name": "Value", "data": series}]

        cleaned_series: List[Dict[str, Any]] = []
        for i, s in enumerate(series):
            if not isinstance(s, dict) or "data" not in s:
                return f"[Error] series[{i}] must be an object with 'data' field."
            s_name = str(s.get("name") or f"Series {i + 1}").strip()
            raw_data = s.get("data", [])
            if not isinstance(raw_data, list):
                return f"[Error] series[{i}] 'data' must be a list."
            if len(raw_data) != len(labels):
                return (
                    f"[Error] series[{i}] 'data' length ({len(raw_data)}) "
                    f"must match labels length ({len(labels)})."
                )

            clean_nums = []
            for v in raw_data:
                if v is None:
                    clean_nums.append(0.0)
                elif isinstance(v, (int, float)):
                    clean_nums.append(float(v))
                elif isinstance(v, str):
                    # Clean out commas, dollar signs, spaces, etc.
                    import re
                    cleaned_str = re.sub(r"[^\d.-]", "", v.strip())
                    try:
                        clean_nums.append(float(cleaned_str))
                    except ValueError:
                        clean_nums.append(0.0)
                else:
                    clean_nums.append(0.0)

            cleaned_series.append({
                "name": s_name,
                "data": clean_nums,
            })

        # Build the artifact payload (returned separately by agent loop)
        chart_payload = {
            "chart_type": chart_type,
            "title": title,
            "labels": [str(l) for l in labels],
            "series": cleaned_series,
        }
        self._last_artifact = {
            "kind": "chart",
            "type": "chart",
            "data": chart_payload,
            **chart_payload,
        }

        series_names = ", ".join(s["name"] for s in series)
        return (
            f"Chart '{title}' ({chart_type}) created with {len(labels)} labels "
            f"and {len(series)} series: {series_names}."
        )

    def get_artifact(self) -> Dict[str, Any]:
        """Return the last generated chart artifact."""
        return getattr(self, "_last_artifact", {})
