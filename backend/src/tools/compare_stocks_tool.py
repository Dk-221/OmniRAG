"""
compare_stocks_tool – compare historical performance of 2 to 4 stocks via yfinance.

Calculates normalized percentage change or base-100 prices over a period (1mo, 3mo, 6mo, 1y).
Returns a textual summary for the LLM and creates a structured line chart artifact for the frontend.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import yfinance as yf

from src.tools._base import BaseTool, truncate

logger = logging.getLogger(__name__)

# Common Indian stock symbols to auto-suggest .NS
INDIAN_STOCKS_HINTS = {
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "BHARTIARTL",
    "ITC", "KOTAKBANK", "LT", "HINDUNILVR", "AXISBANK", "BAJFINANCE",
    "MARUTI", "TATAMOTORS", "TATASTEEL", "WIPRO", "HCLTECH", "SUNPHARMA",
    "NTPC", "POWERGRID", "TITAN", "ULTRACEMCO", "ADANIENT", "ADANIPORTS",
}

_VALID_PERIODS = {"5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "ytd", "max"}


def normalize_ticker(ticker: str) -> str:
    """Normalize ticker and append .NS for recognized Indian tickers if suffix missing."""
    t = ticker.strip().upper()
    if "." not in t and t in INDIAN_STOCKS_HINTS:
        return f"{t}.NS"
    return t


class CompareStocksTool(BaseTool):
    """Compare performance of 2 to 4 stocks over a given period and return a line chart artifact."""

    name = "compare_stocks"
    description = (
        "Compare the historical performance of 2 to 4 stock tickers over a period (e.g., '1mo', '3mo', '6mo', '1y'). "
        "Returns a performance summary and generates a normalized line chart artifact for visualization."
    )
    parameters = {
        "type": "object",
        "properties": {
            "tickers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of 2 to 4 stock ticker symbols (e.g. ['AAPL', 'MSFT'] or ['RELIANCE.NS', 'TCS.NS']).",
            },
            "period": {
                "type": "string",
                "enum": ["5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "ytd"],
                "description": "Historical time period. Default is '6mo'.",
            },
        },
        "required": ["tickers"],
    }
    category = "finance"

    def __init__(self) -> None:
        self._last_artifact: Optional[Dict[str, Any]] = None

    def run(  # type: ignore[override]
        self,
        tickers: List[str],
        period: str = "6mo",
        **_: Any,
    ) -> str:
        """Fetch historical prices, normalize to base 100, and create line chart artifact."""
        self._last_artifact = None

        if not isinstance(tickers, list) or len(tickers) < 2 or len(tickers) > 4:
            return "[Error] Please provide between 2 and 4 tickers to compare."

        period = period.lower().strip()
        if period not in _VALID_PERIODS:
            period = "6mo"

        normalized_tickers = [normalize_ticker(t) for t in tickers]
        logger.info("Comparing stocks: %s over period %s", normalized_tickers, period)

        data_series: List[Dict[str, Any]] = []
        all_candles: Dict[str, List[Dict[str, Any]]] = {}
        labels: List[str] = []
        summaries: List[str] = []

        try:
            for ticker in normalized_tickers:
                t = yf.Ticker(ticker)
                hist = t.history(period=period)
                if hist.empty or "Close" not in hist.columns:
                    # Retry with .NS if not present
                    if "." not in ticker:
                        t = yf.Ticker(f"{ticker}.NS")
                        hist = t.history(period=period)
                        if not hist.empty:
                            ticker = f"{ticker}.NS"

                if hist.empty or "Close" not in hist.columns:
                    summaries.append(f"{ticker}: No historical data found.")
                    continue

                closes = hist["Close"].dropna()
                if len(closes) < 2:
                    summaries.append(f"{ticker}: Insufficient data points.")
                    continue

                opens = hist["Open"].reindex(closes.index).fillna(closes)
                highs = hist["High"].reindex(closes.index).fillna(closes)
                lows = hist["Low"].reindex(closes.index).fillna(closes)

                first_val = float(closes.iloc[0])
                last_val = float(closes.iloc[-1])
                pct_return = ((last_val - first_val) / first_val) * 100

                # Base 100 normalization
                norm_values = [round((float(v) / first_val) * 100, 2) for v in closes]

                # Sample up to ~25-30 data points for clean charting
                step = max(1, len(norm_values) // 25)
                sampled_values = norm_values[::step]
                date_labels = [d.strftime("%Y-%m-%d") for d in closes.index[::step]]

                if not labels:
                    labels = date_labels

                data_series.append({
                    "name": ticker,
                    "data": sampled_values[:len(labels)],
                })

                # Build floating candles
                ticker_candles = []
                for idx in range(0, len(closes), step):
                    d_str = closes.index[idx].strftime("%Y-%m-%d")
                    o = float(opens.iloc[idx])
                    h = float(highs.iloc[idx])
                    l = float(lows.iloc[idx])
                    c = float(closes.iloc[idx])

                    ticker_candles.append({
                        "date": d_str,
                        "open": round((o / first_val) * 100, 2),
                        "high": round((h / first_val) * 100, 2),
                        "low": round((l / first_val) * 100, 2),
                        "close": round((c / first_val) * 100, 2),
                        "raw_open": round(o, 2),
                        "raw_high": round(h, 2),
                        "raw_low": round(l, 2),
                        "raw_close": round(c, 2),
                    })
                all_candles[ticker] = ticker_candles[:len(labels)]

                summaries.append(
                    f"{ticker}: Start={first_val:.2f}, End={last_val:.2f}, Return={pct_return:+.2f}%"
                )

            if not data_series:
                return f"Could not retrieve historical data for tickers: {', '.join(normalized_tickers)}"

            # Ensure all series match label length
            min_len = min(len(labels), *(len(s["data"]) for s in data_series))
            chart_labels = labels[:min_len]
            for s in data_series:
                s["data"] = s["data"][:min_len]
            for t_k in all_candles:
                all_candles[t_k] = all_candles[t_k][:min_len]

            chart_payload = {
                "chart_type": "candle",
                "title": f"Stock Price Comparison ({', '.join(normalized_tickers)}) - {period}",
                "labels": chart_labels,
                "series": data_series,
                "candles": all_candles,
            }

            self._last_artifact = {
                "kind": "chart",
                "data": chart_payload,
            }

            lines = [
                f"Comparison over {period} (Normalized to Base 100):",
                *summaries,
                f"Generated floating candles chart artifact for {len(data_series)} stocks.",
            ]
            return "\n".join(lines)

        except Exception as exc:
            logger.exception("compare_stocks failed: %s", exc)
            return f"[Tool error] compare_stocks: {exc}"
