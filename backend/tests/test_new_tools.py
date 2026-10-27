"""
Smoke tests for all 15 new tools, tool router, and sandbox security.

Run with:
    python -m pytest tests/test_new_tools.py -v
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from src.tools.air_quality_tool import AirQualityTool
from src.tools.analyze_data_tool import AnalyzeDataTool
from src.tools.compare_stocks_tool import CompareStocksTool
from src.tools.crypto_price_tool import CryptoPriceTool
from src.tools.currency_convert_tool import CurrencyConvertTool
from src.tools.geocode_place_tool import GeocodePlaceTool
from src.tools.get_news_tool import GetNewsTool
from src.tools.make_chart_tool import MakeChartTool
from src.tools.read_url_tool import ReadUrlTool
from src.tools.remember_tool import RememberTool
from src.tools.run_python_tool import RunPythonTool
from src.tools.search_papers_tool import SearchPapersTool
from src.tools.tech_news_tool import TechNewsTool
from src.tools.wikipedia_lookup_tool import WikipediaLookupTool
from src.tools.youtube_summary_tool import YouTubeSummaryTool
from src.router import select_tools, get_all_tools
from src.config import settings


# ── 1. Python sandbox & escape tests ─────────────────────────────────────
def test_run_python_basic():
    tool = RunPythonTool()
    res = tool.run("x = 10\ny = 25\nresult = x * y\nprint(f'Computed {result}')")
    assert "250" in res
    art = tool.get_artifact()
    assert art is not None
    assert art["kind"] == "code"
    assert art["data"]["code"] is not None


def test_run_python_sandbox_escapes():
    tool = RunPythonTool()
    # os module blocked
    res = tool.run("import os\nresult = os.listdir('.')")
    assert "blocked" in res.lower() or "error" in res.lower()

    # sys module blocked
    res = tool.run("import sys\nresult = sys.version")
    assert "blocked" in res.lower() or "error" in res.lower()

    # subprocess blocked
    res = tool.run("import subprocess\nsubprocess.run(['echo', 'pwned'])")
    assert "blocked" in res.lower() or "error" in res.lower()

    # socket blocked
    res = tool.run("import socket\ns = socket.socket()")
    assert "blocked" in res.lower() or "error" in res.lower()

    # shutil blocked
    res = tool.run("import shutil\nshutil.rmtree('.')")
    assert "blocked" in res.lower() or "error" in res.lower()


# ── 2. Data analysis with DuckDB ─────────────────────────────────────────
def test_analyze_data():
    settings.datasets_path.mkdir(parents=True, exist_ok=True)
    sample_csv = settings.datasets_path / "test_sales.csv"
    sample_csv.write_text("product,quantity,price\nApples,10,2.5\nBananas,20,1.2\nCherries,15,4.0\n", encoding="utf-8")

    tool = AnalyzeDataTool()
    # With explicit SQL
    res = tool.run(
        question="What is the total quantity?",
        filename="test_sales.csv",
        sql="SELECT SUM(quantity) as total_qty FROM data_table",
    )
    assert "45" in res
    art = tool.get_artifact()
    assert art is not None
    assert art["kind"] == "table"
    assert "columns" in art["data"]
    assert "rows" in art["data"]


# ── 3. Make chart tool ────────────────────────────────────────────────────
def test_make_chart():
    tool = MakeChartTool()
    res = tool.run(
        title="Q1 Revenue",
        chart_type="bar",
        labels=["Jan", "Feb", "Mar"],
        series=[{"name": "2026", "data": [100, 150, 200]}],
    )
    assert "Q1 Revenue" in res and "bar" in res
    art = tool.get_artifact()
    assert art is not None
    assert art["type"] == "chart"
    assert art["chart_type"] == "bar"
    assert art["labels"] == ["Jan", "Feb", "Mar"]

    # Invalid chart type
    invalid = tool.run("Bad", "scatter", ["A"], [{"name": "S", "data": [1]}])
    assert "[Error]" in invalid


# ── 4. SSRF protection in read_url ────────────────────────────────────────
def test_read_url_ssrf():
    tool = ReadUrlTool()
    # Block localhost
    res = tool.run("http://localhost:8000/secret")
    assert "Blocked" in res or "error" in res.lower()

    # Block 127.0.0.1
    res = tool.run("http://127.0.0.1:8000/")
    assert "Blocked" in res or "error" in res.lower()

    # Block private IP
    res = tool.run("http://192.168.1.1/admin")
    assert "Blocked" in res or "error" in res.lower()

    # Block non-http schemes
    res = tool.run("file:///C:/Windows/win.ini")
    assert "Blocked" in res or "error" in res.lower()


# ── 5. YouTube summary (graceful fallback) ────────────────────────────────
def test_youtube_summary_fallback():
    tool = YouTubeSummaryTool()
    res = tool.run("https://www.youtube.com/watch?v=invalid_id_12345")
    assert "transcript" in res.lower() or "error" in res.lower() or "could not" in res.lower()


# ── 6. Wikipedia lookup ───────────────────────────────────────────────────
def test_wikipedia_lookup():
    tool = WikipediaLookupTool()
    res = tool.run("Python (programming language)")
    assert "Python" in res or "programming" in res or "error" in res.lower()


# ── 7. arXiv paper search ─────────────────────────────────────────────────
def test_search_papers():
    tool = SearchPapersTool()
    res = tool.run("quantum computing")
    assert len(res) > 20


# ── 8. Tech news (Hacker News) ────────────────────────────────────────────
def test_tech_news():
    tool = TechNewsTool()
    res = tool.run()
    assert len(res) > 20


# ── 9. Google News RSS ────────────────────────────────────────────────────
def test_get_news():
    tool = GetNewsTool()
    res = tool.run("technology")
    assert len(res) > 20
    art = tool.get_artifact()
    if art:
        assert art["kind"] == "news"


# ── 10. Currency converter ────────────────────────────────────────────────
def test_currency_convert():
    tool = CurrencyConvertTool()
    res = tool.run(100.0, "USD", "EUR")
    assert "USD" in res and "EUR" in res


# ── 11. Crypto price ──────────────────────────────────────────────────────
def test_crypto_price():
    tool = CryptoPriceTool()
    res = tool.run("bitcoin")
    assert "Bitcoin" in res or "BTC" in res or "USD" in res


# ── 12. Air quality ───────────────────────────────────────────────────────
def test_air_quality():
    tool = AirQualityTool()
    res = tool.run("London")
    assert "Air Quality" in res or "AQI" in res


# ── 13. Geocoding ─────────────────────────────────────────────────────────
def test_geocode_place():
    tool = GeocodePlaceTool()
    res = tool.run("Eiffel Tower Paris")
    assert "Coordinates" in res or "Latitude" in res or "Paris" in res


# ── 14. Compare stocks ────────────────────────────────────────────────────
def test_compare_stocks():
    tool = CompareStocksTool()
    res = tool.run(["AAPL", "MSFT"], period="1mo")
    assert "AAPL" in res
    art = tool.get_artifact()
    if art:
        assert art["kind"] == "chart"
        assert art["data"]["chart_type"] == "line"


# ── 15. Remember tool & memories ──────────────────────────────────────────
def test_remember_and_memories():
    tool = RememberTool()
    res = tool.run("The user preferred currency is INR")
    assert "Successfully remembered" in res

    from src.rag import list_memories, delete_memory
    mems = list_memories()
    assert any("INR" in m["fact"] for m in mems)

    # Clean up
    for m in mems:
        if "INR" in m["fact"]:
            delete_memory(m["id"])


# ── 16. Tool Router ───────────────────────────────────────────────────────
def test_tool_router():
    # Mandatory tools always present
    selected = select_tools("Hello world", max_tools=6)
    names = [t.name for t in selected]
    assert "search_knowledge_base" in names
    assert "web_search" in names
    assert len(selected) <= 6

    # Test keyword matching: stocks and news
    stock_news_tools = select_tools("price of reliance and the news", max_tools=6)
    sn_names = [t.name for t in stock_news_tools]
    assert "search_knowledge_base" in sn_names
    assert "web_search" in sn_names
    assert "get_stock_data" in sn_names or "compare_stocks" in sn_names
    assert "get_news" in sn_names or "tech_news" in sn_names
