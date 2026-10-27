"""
finance_tool – real-time stock data via yfinance (no API key required).

Provides: current price, daily change %, day range, 52-week range,
market cap, volume, and a short company summary.
Supports US, NSE (.NS), and BSE (.BO) tickers with auto-suggestion.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import yfinance as yf

from src.tools._base import BaseTool

logger = logging.getLogger(__name__)

INDIAN_STOCKS_HINTS = {
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "BHARTIARTL",
    "ITC", "KOTAKBANK", "LT", "HINDUNILVR", "AXISBANK", "BAJFINANCE",
    "MARUTI", "TATAMOTORS", "TATASTEEL", "WIPRO", "HCLTECH", "SUNPHARMA",
    "NTPC", "POWERGRID", "TITAN", "ULTRACEMCO", "ADANIENT", "ADANIPORTS",
}


def _fmt_large(n: float | None) -> str:
    """Format large numbers with K/M/B suffixes."""
    if n is None:
        return "N/A"
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.2f}K"
    return str(n)


class FinanceTool(BaseTool):
    """Retrieve real-time stock market data and financial overview for a company."""

    name = "get_stock_data"
    description = (
        "Retrieve real-time stock prices, trading ranges, and key financial metrics for a company. "
        "Supports US (AAPL, TSLA) and Indian NSE/BSE tickers (e.g. RELIANCE.NS, TCS.BO)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": (
                    "The stock ticker symbol (e.g. 'AAPL', 'RELIANCE.NS', 'TCS.NS', 'MSFT'). "
                    "For Indian equities, specify '.NS' for NSE or '.BO' for BSE."
                ),
            }
        },
        "required": ["ticker"],
    }
    category = "finance"

    def __init__(self) -> None:
        self._last_artifact: Optional[Dict[str, Any]] = None

    def run(self, ticker: str, **_: Any) -> str:  # type: ignore[override]
        """Fetch and format stock data for *ticker*."""
        self._last_artifact = None
        orig_ticker = ticker.strip().upper()
        ticker = orig_ticker

        # Auto-suggest .NS for common Indian tickers without exchange suffix
        if "." not in ticker and ticker in INDIAN_STOCKS_HINTS:
            ticker = f"{ticker}.NS"

        logger.info("Fetching stock data for %s", ticker)

        info = {}
        try:
            t = yf.Ticker(ticker)
            info = t.info
        except Exception:
            info = {}

        # Fallback: if not found and has no exchange suffix, try .NS
        if (not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None) and "." not in ticker:
            try:
                ns_ticker = f"{ticker}.NS"
                t_ns = yf.Ticker(ns_ticker)
                if t_ns.info and (t_ns.info.get("regularMarketPrice") or t_ns.info.get("currentPrice")):
                    ticker = ns_ticker
                    info = t_ns.info
            except Exception:
                pass

        if not info or (info.get("regularMarketPrice") is None and info.get("currentPrice") is None):
            try:
                fast = yf.Ticker(ticker).fast_info
                price = fast.last_price
                if price is not None:
                    self._last_artifact = {
                        "kind": "stock",
                        "data": {
                            "ticker": ticker,
                            "price": round(float(price), 2),
                            "change_pct": 0.0,
                            "day_low": None,
                            "day_high": None,
                            "currency": "USD",
                        },
                    }
                    return (
                        f"Ticker: {ticker}\n"
                        f"Current Price: {price:.2f}\n"
                        "(Limited data – market may be closed or non-US)"
                    )
            except Exception:
                pass

            suggestion = f" Did you mean '{orig_ticker}.NS'?" if "." not in orig_ticker else ""
            return f"No data found for ticker '{orig_ticker}'.{suggestion} Please verify the symbol."

        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        change_pct = (
            ((current_price - prev_close) / prev_close * 100)
            if current_price and prev_close
            else None
        )
        day_low = info.get("dayLow") or info.get("regularMarketDayLow")
        day_high = info.get("dayHigh") or info.get("regularMarketDayHigh")
        week52_low = info.get("fiftyTwoWeekLow")
        week52_high = info.get("fiftyTwoWeekHigh")
        market_cap = info.get("marketCap")
        volume = info.get("volume") or info.get("regularMarketVolume")
        summary = (info.get("longBusinessSummary") or "")[:250]
        company = info.get("longName") or info.get("shortName") or ticker
        currency = info.get("currency", "USD")
        market_state = info.get("marketState", "unknown")

        # Emit stock artifact shape: {ticker, price, change_pct, day_low, day_high, currency}
        self._last_artifact = {
            "kind": "stock",
            "data": {
                "ticker": ticker,
                "price": round(float(current_price), 2) if current_price else None,
                "change_pct": round(float(change_pct), 2) if change_pct is not None else None,
                "day_low": round(float(day_low), 2) if day_low else None,
                "day_high": round(float(day_high), 2) if day_high else None,
                "currency": currency,
            },
        }

        lines = [
            f"Company: {company} ({ticker})",
            f"Market State: {market_state}",
            f"Current Price: {currency} {current_price:.2f}" if current_price else "Current Price: N/A",
            (
                f"Daily Change: {change_pct:+.2f}%"
                if change_pct is not None
                else "Daily Change: N/A"
            ),
            f"Day Range: {day_low} – {day_high}",
            f"52-Week Range: {week52_low} – {week52_high}",
            f"Market Cap: {_fmt_large(market_cap)}",
            f"Volume: {_fmt_large(volume)}",
        ]
        if summary:
            lines.append(f"Summary: {summary}")

        return "\n".join(lines)
