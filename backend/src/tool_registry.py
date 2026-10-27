"""
tool_registry – assembles all agent tools into a single list.

Import ``TOOLS`` (list of BaseTool instances) and ``TOOL_SPECS`` (the
Groq-compatible tool spec list) from here.
"""

from __future__ import annotations

import logging
from typing import Dict, List

from src.tools._base import BaseTool
from src.tools.air_quality_tool import AirQualityTool
from src.tools.analyze_data_tool import AnalyzeDataTool
from src.tools.calculator_tool import CalculatorTool
from src.tools.compare_stocks_tool import CompareStocksTool
from src.tools.crypto_price_tool import CryptoPriceTool
from src.tools.currency_convert_tool import CurrencyConvertTool
from src.tools.finance_tool import FinanceTool
from src.tools.geocode_place_tool import GeocodePlaceTool
from src.tools.get_news_tool import GetNewsTool
from src.tools.knowledge_base_tool import KnowledgeBaseTool
from src.tools.make_chart_tool import MakeChartTool
from src.tools.read_url_tool import ReadUrlTool
from src.tools.remember_tool import RememberTool
from src.tools.run_python_tool import RunPythonTool
from src.tools.search_papers_tool import SearchPapersTool
from src.tools.tech_news_tool import TechNewsTool
from src.tools.weather_tool import WeatherTool
from src.tools.web_search_tool import WebSearchTool
from src.tools.wikipedia_lookup_tool import WikipediaLookupTool
from src.tools.youtube_summary_tool import YouTubeSummaryTool

logger = logging.getLogger(__name__)

# ── instantiate all tools ─────────────────────────────────────────────────
TOOLS: List[BaseTool] = [
    # 1. Knowledge
    KnowledgeBaseTool(),
    RememberTool(),
    # 2. Web & Reading
    WebSearchTool(),
    ReadUrlTool(),
    YouTubeSummaryTool(),
    WikipediaLookupTool(),
    SearchPapersTool(),
    TechNewsTool(),
    GetNewsTool(),
    # 3. Finance
    FinanceTool(),
    CompareStocksTool(),
    CurrencyConvertTool(),
    CryptoPriceTool(),
    # 4. Data
    AnalyzeDataTool(),
    MakeChartTool(),
    # 5. Code
    RunPythonTool(),
    # 6. Utility
    CalculatorTool(),
    WeatherTool(),
    AirQualityTool(),
    GeocodePlaceTool(),
]

# Map name → instance for fast lookup in the agent loop
TOOL_MAP: Dict[str, BaseTool] = {t.name: t for t in TOOLS}

# Groq-compatible tool specifications list (all tools)
TOOL_SPECS: List[dict] = [t.to_groq_spec() for t in TOOLS]

logger.info(
    "Tool registry initialised with %d tools: %s",
    len(TOOLS),
    [t.name for t in TOOLS],
)
