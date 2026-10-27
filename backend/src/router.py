"""
router.py – Dynamic tool selection using keyword matching and sentence embeddings.

Selects at most ROUTER_MAX_TOOLS (default 6) for each user message to keep the
Groq context lean and avoid rate limits.
Always includes: search_knowledge_base, web_search.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set

import numpy as np

from src.config import settings
from src.tool_registry import TOOLS, TOOL_MAP
from src.tools._base import BaseTool

logger = logging.getLogger(__name__)

# Mandatory tools that must always be included
MANDATORY_TOOLS: List[str] = ["search_knowledge_base", "web_search"]

# Keyword mappings to boost specific tool relevance
KEYWORD_MAP: Dict[str, List[str]] = {
    # Code & Python
    "run_python": ["python", "code", "script", "execute", "run", "program", "sandbox", "def ", "import "],
    # Data & SQL
    "analyze_data": ["csv", "xlsx", "excel", "dataset", "dataframe", "sql", "table", "rows", "columns", "data file", "query file", "uploaded csv", "my uploaded", "uploaded dataset", "uploaded", "average by", "group by"],
    # Chart
    "make_chart": ["chart", "plot", "graph", "visualize", "bar chart", "line chart", "pie chart", "area chart", "trends"],
    # Web reading
    "read_url": ["http://", "https://", "url", "link", "webpage", "article", "website", "scrape", "read page"],
    "youtube_summary": ["youtube", "video", "transcript", "youtu.be", "watch"],
    "wikipedia_lookup": ["wikipedia", "wiki", "who was", "who is", "what is", "biography", "history of", "overview of"],
    "search_papers": ["paper", "papers", "arxiv", "research", "scientific", "study", "studies", "academic", "journal", "abstract"],
    "tech_news": ["hacker news", "hackernews", "hn", "tech news", "y combinator", "technology news", "tech headlines"],
    "get_news": ["news", "headline", "headlines", "latest", "breaking", "event", "happening", "today's news"],
    # Finance
    "get_stock_data": ["stock", "shares", "price of", "ticker", "market cap", "nasdaq", "nyse", "nse", "bse", "equity", "share price", "valuation"],
    "compare_stocks": ["compare", "vs", "versus", "outperform", "relative to", "performance comparison", "stock comparison"],
    "currency_convert": ["convert", "currency", "exchange rate", "forex", "usd", "eur", "inr", "gbp", "jpy", "dollars to", "rupees"],
    "crypto_price": ["crypto", "bitcoin", "btc", "ethereum", "eth", "solana", "sol", "doge", "coin", "cryptocurrency", "tokens"],
    # Utilities & Live
    "get_weather": ["weather", "temperature", "forecast", "rain", "sunny", "humid", "wind", "climate", "celsius", "degrees"],
    "air_quality": ["air quality", "aqi", "pollution", "pm2.5", "pm10", "smog", "air pollution"],
    "geocode_place": ["geocode", "coordinates", "latitude", "longitude", "where is", "address", "location coordinates"],
    "calculate": ["calculate", "compute", "math", "sqrt", "+", "-", "*", "/", "percentage", "algebra", "eval"],
    # Memory
    "remember": [
        "remember", "remember that", "save my", "note down", "store this",
        "my name is", "my favorite", "my preference", "who am i", "my name",
        "what is my", "user name", "name of user", "what is the name", "about me", "stored memory"
    ],
}

# Cached embeddings for tool descriptions
_tool_embeddings: Optional[Dict[str, np.ndarray]] = None


def _get_tool_embeddings() -> Dict[str, np.ndarray]:
    """Compute and cache embeddings for all registered tool descriptions."""
    global _tool_embeddings
    if _tool_embeddings is None:
        from src.rag import _get_embedder
        embedder = _get_embedder()
        _tool_embeddings = {}
        for tool in TOOLS:
            # Combine tool name, category, and description for rich semantic embedding
            text = f"{tool.name} ({tool.category}): {tool.description}"
            emb = embedder.encode(text, show_progress_bar=False)
            # Normalize for cosine similarity
            norm = np.linalg.norm(emb)
            if norm > 0:
                emb = emb / norm
            _tool_embeddings[tool.name] = emb
    return _tool_embeddings


def select_tools(
    user_message: str,
    max_tools: Optional[int] = None,
) -> List[BaseTool]:
    """
    Select at most `max_tools` tools for the given user message.

    Always includes:
        - search_knowledge_base
        - web_search

    The remaining slots are filled by combining keyword matching and
    sentence embedding cosine similarity.
    """
    if max_tools is None:
        max_tools = settings.router_max_tools

    msg_lower = user_message.lower()

    # 1. Base mandatory tools
    selected_names: Set[str] = set()
    for name in MANDATORY_TOOLS:
        if name in TOOL_MAP:
            selected_names.add(name)

    # If user provided an HTTP/HTTPS URL, always include read_url
    if ("http://" in msg_lower or "https://" in msg_lower) and "read_url" in TOOL_MAP:
        selected_names.add("read_url")

    remaining_capacity = max(0, max_tools - len(selected_names))
    if remaining_capacity == 0:
        return [TOOL_MAP[n] for n in selected_names]

    # 2. Score candidates by keyword matches
    keyword_scores: Dict[str, float] = {}
    for tool_name, keywords in KEYWORD_MAP.items():
        if tool_name in selected_names:
            continue
        score = 0.0
        for kw in keywords:
            if kw in msg_lower:
                score += 1.0
        if score > 0:
            keyword_scores[tool_name] = score

    # 3. Score candidates by semantic embedding cosine similarity
    try:
        from src.rag import _get_embedder
        embedder = _get_embedder()
        q_emb = embedder.encode(user_message, show_progress_bar=False)
        q_norm = np.linalg.norm(q_emb)
        if q_norm > 0:
            q_emb = q_emb / q_norm

        tool_embs = _get_tool_embeddings()
        semantic_scores: Dict[str, float] = {}
        for tool_name, t_emb in tool_embs.items():
            if tool_name in selected_names:
                continue
            cos_sim = float(np.dot(q_emb, t_emb))
            semantic_scores[tool_name] = cos_sim
    except Exception as exc:
        logger.warning("Router semantic scoring fallback to keywords only: %s", exc)
        semantic_scores = {}

    # 4. Combine scores (keyword boost + semantic similarity)
    candidates: List[tuple[str, float]] = []
    for tool in TOOLS:
        t_name = tool.name
        if t_name in selected_names:
            continue
        kw_score = keyword_scores.get(t_name, 0.0)
        sem_score = semantic_scores.get(t_name, 0.0)
        # Heavy boost for exact keyword matches (1.0 keyword match ≈ +0.5 similarity)
        total_score = (kw_score * 0.5) + sem_score
        candidates.append((t_name, total_score))

    candidates.sort(key=lambda x: x[1], reverse=True)

    # 5. Pick top candidates to fill remaining capacity
    for t_name, score in candidates[:remaining_capacity]:
        selected_names.add(t_name)

    selected_tools = [TOOL_MAP[n] for n in selected_names if n in TOOL_MAP]
    logger.info(
        "Router offered %d tools: %s (query: %r)",
        len(selected_tools),
        [t.name for t in selected_tools],
        user_message[:60],
    )
    return selected_tools


def get_all_tools() -> List[BaseTool]:
    """Return all available tools for fallback retry."""
    return list(TOOLS)
