"""
crypto_price_tool – real-time cryptocurrency prices via CoinGecko public API.

No API key required for the public endpoint. Returns price in USD and INR,
24-hour change percentage, and market cap. Caches for 5 minutes.
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
_USER_AGENT = "OmniRAG-Bot/1.0 (educational project)"
_API = "https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd,inr&include_24hr_change=true&include_market_cap=true"
_SEARCH_API = "https://api.coingecko.com/api/v3/search?query={query}"

# Common coin name → CoinGecko ID mappings
_COIN_MAP = {
    "bitcoin": "bitcoin", "btc": "bitcoin",
    "ethereum": "ethereum", "eth": "ethereum",
    "solana": "solana", "sol": "solana",
    "cardano": "cardano", "ada": "cardano",
    "dogecoin": "dogecoin", "doge": "dogecoin",
    "xrp": "ripple", "ripple": "ripple",
    "bnb": "binancecoin", "binance": "binancecoin",
    "usdt": "tether", "tether": "tether",
    "usdc": "usd-coin",
    "polkadot": "polkadot", "dot": "polkadot",
    "shiba": "shiba-inu", "shib": "shiba-inu",
    "avalanche": "avalanche-2", "avax": "avalanche-2",
    "polygon": "matic-network", "matic": "matic-network",
    "chainlink": "chainlink", "link": "chainlink",
    "litecoin": "litecoin", "ltc": "litecoin",
}


def _resolve_coin_id(coin: str) -> str | None:
    """Map a coin name/ticker to a CoinGecko ID."""
    key = coin.lower().strip()
    if key in _COIN_MAP:
        return _COIN_MAP[key]
    # Try searching CoinGecko
    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(
                _SEARCH_API.format(query=key),
                headers={"User-Agent": _USER_AGENT},
            )
            resp.raise_for_status()
            coins = resp.json().get("coins", [])
            if coins:
                return coins[0]["id"]
    except Exception:
        pass
    return None


class CryptoPriceTool(BaseTool):
    """Get real-time cryptocurrency price in USD and INR with 24-hour change using CoinGecko's free public API."""

    name = "crypto_price"
    description = (
        "Look up the current price, 24h change, and market cap for any cryptocurrency "
        "in USD and INR. Use coin names like 'bitcoin', 'ethereum', 'solana', or tickers like 'BTC'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "coin": {
                "type": "string",
                "description": "Coin name or ticker (e.g. 'bitcoin', 'BTC', 'ethereum', 'ETH').",
            }
        },
        "required": ["coin"],
    }
    category = "finance"

    def run(self, coin: str, **_: Any) -> str:  # type: ignore[override]
        """Fetch CoinGecko price data for *coin*."""
        coin_raw = coin.strip()
        cache_key = f"crypto:{coin_raw.lower()}"
        if cache_key in _CACHE:
            return _CACHE[cache_key]

        coin_id = _resolve_coin_id(coin_raw)
        if not coin_id:
            return (
                f"[Error] Unknown coin '{coin_raw}'. "
                "Try full names like 'bitcoin', 'ethereum', 'solana'."
            )

        url = _API.format(coin_id=coin_id)
        try:
            with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
                resp = client.get(url, headers={"User-Agent": _USER_AGENT})
                resp.raise_for_status()
                data = resp.json()
        except httpx.TimeoutException:
            return "[Error] CoinGecko request timed out."
        except Exception as exc:
            return f"[Error] Crypto price fetch failed: {exc}"

        info = data.get(coin_id, {})
        if not info:
            return f"[Error] No data returned for '{coin_id}'."

        usd = info.get("usd", "N/A")
        inr = info.get("inr", "N/A")
        chg_usd = info.get("usd_24h_change", None)
        mkt_usd = info.get("usd_market_cap", None)

        def _fmt(v: float | None) -> str:
            if v is None:
                return "N/A"
            if v >= 1_000_000_000:
                return f"${v/1e9:.2f}B"
            if v >= 1_000_000:
                return f"${v/1e6:.2f}M"
            return f"${v:,.2f}"

        lines = [
            f"Coin: {coin_raw.upper()} ({coin_id})",
            f"Price (USD): ${usd:,.4f}" if isinstance(usd, (int, float)) else f"Price (USD): {usd}",
            f"Price (INR): ₹{inr:,.2f}" if isinstance(inr, (int, float)) else f"Price (INR): {inr}",
            f"24h Change: {chg_usd:+.2f}%" if chg_usd is not None else "24h Change: N/A",
            f"Market Cap: {_fmt(mkt_usd)}",
        ]

        result = "\n".join(lines)
        _CACHE[cache_key] = result
        return result
