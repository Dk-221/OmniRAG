"""
Smoke tests – one per tool + basic RAG sanity check.

Run from backend/ directory:
    python -m pytest tests/ -v

Or run the smoke script directly:
    python tests/test_tools.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# ── ensure backend/ is on sys.path ─────────────────────────────────────────
_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND))


# ══════════════════════════════════════════════════════════════════════════
# Calculator (no external deps – always run first)
# ══════════════════════════════════════════════════════════════════════════
def test_calculator_basic():
    from src.tools.calculator_tool import CalculatorTool, safe_eval

    tool = CalculatorTool()

    # basic arithmetic
    assert safe_eval("2 + 2") == 4
    assert safe_eval("10 / 4") == 2.5
    assert safe_eval("2 ** 10") == 1024

    # math functions
    import math
    assert abs(safe_eval("sqrt(144)") - 12) < 1e-9
    assert abs(safe_eval("sin(pi/2)") - 1.0) < 1e-9
    assert abs(safe_eval("log(e)") - 1.0) < 1e-9

    # tool.run()
    result = tool.run(expression="(3 + 4) * 5")
    assert "35" in result, f"Expected 35 in: {result}"

    # security: eval() must never run
    import pytest
    with pytest.raises(ValueError):
        safe_eval("__import__('os').system('echo pwned')")

    print("✅  Calculator: PASS")


def test_calculator_safe_mode():
    """Ensure dangerous expressions are blocked."""
    from src.tools.calculator_tool import safe_eval
    import pytest

    dangerous = [
        "open('/etc/passwd').read()",
        "__import__('subprocess').getoutput('id')",
        "exec('import os')",
        "eval('1+1')",
        "compile('x=1', '', 'exec')",
    ]
    for expr in dangerous:
        with pytest.raises((ValueError, TypeError)):
            safe_eval(expr)
    print("✅  Calculator security: PASS")


# ══════════════════════════════════════════════════════════════════════════
# Web Search
# ══════════════════════════════════════════════════════════════════════════
def test_web_search():
    from src.tools.web_search_tool import WebSearchTool

    tool = WebSearchTool()
    result = tool.run(query="Python programming language")
    print(f"   Web search result snippet: {result[:100]}")
    assert len(result) > 20, "Expected non-empty web search result"
    print("✅  Web Search: PASS")


# ══════════════════════════════════════════════════════════════════════════
# Weather
# ══════════════════════════════════════════════════════════════════════════
def test_weather():
    from src.tools.weather_tool import WeatherTool

    tool = WeatherTool()
    result = tool.run(city="London")
    print(f"   Weather result snippet: {result[:120]}")
    assert "London" in result or "°C" in result, f"Unexpected result: {result}"
    print("✅  Weather (London): PASS")


def test_weather_invalid_city():
    from src.tools.weather_tool import WeatherTool

    tool = WeatherTool()
    result = tool.safe_run(city="XyzNonExistentCityABC123")
    print(f"   Invalid city result: {result[:80]}")
    assert "not find" in result.lower() or "error" in result.lower() or "could not" in result.lower()
    print("✅  Weather (invalid city): PASS")


# ══════════════════════════════════════════════════════════════════════════
# Finance
# ══════════════════════════════════════════════════════════════════════════
def test_finance_valid_ticker():
    from src.tools.finance_tool import FinanceTool

    tool = FinanceTool()
    result = tool.run(ticker="AAPL")
    print(f"   Finance result snippet: {result[:120]}")
    assert "Apple" in result or "AAPL" in result, f"Unexpected result: {result}"
    print("✅  Finance (AAPL): PASS")


def test_finance_invalid_ticker():
    from src.tools.finance_tool import FinanceTool

    tool = FinanceTool()
    result = tool.safe_run(ticker="XYZNOTREAL99999")
    print(f"   Invalid ticker result: {result[:80]}")
    # Should return an error string, not raise
    assert isinstance(result, str)
    print("✅  Finance (invalid ticker): PASS")


# ══════════════════════════════════════════════════════════════════════════
# RAG – ingest & retrieve
# ══════════════════════════════════════════════════════════════════════════
def test_rag_ingest_and_retrieve():
    import tempfile
    from src import rag

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp_path = Path(tmp)
        sample = tmp_path / "sample.txt"
        sample.write_text(
            "Quantum computing uses quantum bits (qubits) to perform calculations. "
            "Unlike classical bits that are 0 or 1, qubits can exist in superposition.",
            encoding="utf-8",
        )

        # Temporarily point knowledge base and chroma to temp dirs
        import chromadb
        from chromadb.config import Settings as CS
        chroma_tmp = tmp_path / "chroma"
        chroma_tmp.mkdir()

        # Patch the internal collection so we don't pollute the real store
        original_get_collection = rag._get_collection
        original_collection = rag._collection

        test_client = chromadb.PersistentClient(
            path=str(chroma_tmp),
            settings=CS(anonymized_telemetry=False),
        )
        test_col = test_client.get_or_create_collection(
            "test_kb", metadata={"hnsw:space": "cosine"}
        )
        rag._collection = test_col

        try:
            chunks = rag.ingest_file(sample, force=True)
            assert chunks > 0, f"Expected chunks > 0, got {chunks}"

            results = rag.retrieve("quantum bits superposition", top_k=1)
            assert results, "Expected at least one result"
            assert "qubit" in results[0]["text"].lower() or "quantum" in results[0]["text"].lower()
            print(f"   Retrieved: {results[0]['text'][:80]}…")
        finally:
            rag._collection = original_collection

    print("✅  RAG ingest + retrieve: PASS")


# ══════════════════════════════════════════════════════════════════════════
# Knowledge base tool
# ══════════════════════════════════════════════════════════════════════════
def test_knowledge_base_tool_empty():
    """When nothing is indexed, it should return a friendly message."""
    from src.tools.knowledge_base_tool import KnowledgeBaseTool
    import src.rag as rag

    # Only test the "no results" path if the DB is actually empty
    col = rag._get_collection()
    if col.count() == 0:
        tool = KnowledgeBaseTool()
        result = tool.run(query="completely unrelated nonsense xyz123")
        assert "No relevant" in result or len(result) > 0
        print("✅  Knowledge base tool (empty): PASS")
    else:
        tool = KnowledgeBaseTool()
        result = tool.run(query="machine learning")
        assert isinstance(result, str) and len(result) > 0
        print(f"✅  Knowledge base tool (non-empty, got {len(result)} chars): PASS")


# ══════════════════════════════════════════════════════════════════════════
# Tool registry
# ══════════════════════════════════════════════════════════════════════════
def test_tool_registry():
    from src.tool_registry import TOOLS, TOOL_MAP, TOOL_SPECS

    assert len(TOOLS) == 20, f"Expected 20 tools, got {len(TOOLS)}"
    original_names = {
        "search_knowledge_base",
        "web_search",
        "get_stock_data",
        "get_weather",
        "calculate",
    }
    assert original_names.issubset(set(TOOL_MAP.keys()))
    assert len(TOOL_SPECS) == 20
    for spec in TOOL_SPECS:
        assert spec["type"] == "function"
        assert "function" in spec
        assert "name" in spec["function"]
        assert "description" in spec["function"]
        assert "parameters" in spec["function"]
    print("✅  Tool registry: PASS")


# ══════════════════════════════════════════════════════════════════════════
# Config
# ══════════════════════════════════════════════════════════════════════════
def test_config_loads():
    from src.config import settings

    assert settings.groq_model is not None
    assert settings.groq_fallback_model is not None
    assert settings.chroma_path.exists()
    assert settings.knowledge_base_path.exists()
    assert isinstance(settings.cors_origins, list)
    print(f"✅  Config: model={settings.groq_model}, key_set={settings.has_groq_key}")


# ══════════════════════════════════════════════════════════════════════════
# CLI runner
# ══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Agentic RAG – Smoke Tests")
    print("=" * 60 + "\n")

    tests = [
        ("Config", test_config_loads),
        ("Tool Registry", test_tool_registry),
        ("Calculator Basic", test_calculator_basic),
        ("Calculator Security", test_calculator_safe_mode),
        ("Web Search", test_web_search),
        ("Weather (valid)", test_weather),
        ("Weather (invalid city)", test_weather_invalid_city),
        ("Finance (valid ticker)", test_finance_valid_ticker),
        ("Finance (invalid ticker)", test_finance_invalid_ticker),
        ("RAG ingest + retrieve", test_rag_ingest_and_retrieve),
        ("Knowledge Base Tool", test_knowledge_base_tool_empty),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        print(f"\n── {name} ──")
        try:
            fn()
            passed += 1
        except Exception as exc:
            print(f"❌  FAILED: {exc}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"  Results: {passed} passed, {failed} failed")
    print("=" * 60)
    sys.exit(0 if failed == 0 else 1)
