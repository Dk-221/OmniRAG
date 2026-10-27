"""
currency_convert_tool – live currency conversion via the Frankfurter API.

No API key required. Frankfurter is a free, open-source exchange rates API.
Caches exchange rates for 5 minutes.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from cachetools import TTLCache

from src.tools._base import BaseTool

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0
_CACHE: TTLCache = TTLCache(maxsize=128, ttl=300)
_USER_AGENT = "OmniRAG-Bot/1.0 (educational project)"
_API = "https://api.frankfurter.dev/v1/latest?amount={amount}&from={frm}&to={to}"
_API_FALLBACK = "https://api.frankfurter.app/latest?amount={amount}&from={frm}&to={to}"


class CurrencyConvertTool(BaseTool):
    """Convert an amount between any two currencies using live Frankfurter exchange rates. No API key required; rates updated daily."""

    name = "currency_convert"
    description = (
        "Convert a monetary amount from one currency to another using live exchange rates. "
        "Use ISO 4217 codes: USD, EUR, GBP, INR, JPY, CAD, AUD, CHF, CNY, etc."
    )
    parameters = {
        "type": "object",
        "properties": {
            "amount": {
                "type": "number",
                "description": "The amount to convert.",
            },
            "from_currency": {
                "type": "string",
                "description": "Source currency code (e.g. 'USD', 'EUR', 'INR').",
            },
            "to_currency": {
                "type": "string",
                "description": "Target currency code (e.g. 'GBP', 'JPY', 'CAD').",
            },
        },
        "required": ["amount", "from_currency", "to_currency"],
    }
    category = "finance"

    def run(self, amount: float, from_currency: str, to_currency: str, **_: Any) -> str:  # type: ignore[override]
        """Convert *amount* from *from_currency* to *to_currency*."""
        frm = from_currency.strip().upper()
        to = to_currency.strip().upper()

        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return f"[Error] Invalid amount: {amount}"

        if frm == to:
            return (
                f"{amount:,.2f} {frm} = {amount:,.4f} {to}\n"
                f"Exchange rate: 1 {frm} = 1.000000 {to}\n"
                f"Rate date: today"
            )

        cache_key = f"fx:{frm}:{to}"
        if cache_key in _CACHE:
            unit_rate, date = _CACHE[cache_key]
            converted = amount * unit_rate
            return (
                f"{amount:,.2f} {frm} = {converted:,.4f} {to}\n"
                f"Exchange rate: 1 {frm} = {unit_rate:.6f} {to}\n"
                f"Rate date: {date} (cached)"
            )

        data = None
        # Try primary endpoint, then frankfurter.app with follow_redirects=True
        for endpoint in (_API, _API_FALLBACK):
            url = endpoint.format(amount=amount, frm=frm, to=to)
            try:
                with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
                    resp = client.get(url, headers={"User-Agent": _USER_AGENT})
                    if resp.status_code == 200:
                        data = resp.json()
                        break
                    if resp.status_code in (404, 422):
                        break
            except Exception as exc:
                logger.warning("Frankfurter attempt failed (%s): %s", url, exc)

        # Fallback to open.er-api.com if Frankfurter didn't return rates
        if not data or "rates" not in data or to not in data.get("rates", {}):
            try:
                fallback_url = f"https://open.er-api.com/v6/latest/{frm}"
                with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
                    resp = client.get(fallback_url, headers={"User-Agent": _USER_AGENT})
                    if resp.status_code == 200:
                        fb_json = resp.json()
                        if fb_json.get("result") == "success" and to in fb_json.get("rates", {}):
                            rate = fb_json["rates"][to]
                            converted = amount * rate
                            date = fb_json.get("time_last_update_utc", "today")
                            _CACHE[cache_key] = (rate, date)
                            return (
                                f"{amount:,.2f} {frm} = {converted:,.4f} {to}\n"
                                f"Exchange rate: 1 {frm} = {rate:.6f} {to}\n"
                                f"Rate date: {date}"
                            )
            except Exception as exc:
                logger.warning("Secondary exchange rate fallback failed: %s", exc)

        if not data or "rates" not in data:
            return f"[Error] Currency conversion failed for {frm} to {to}. Please check that currency codes are valid ISO codes."

        rates = data.get("rates", {})
        if to not in rates:
            return f"[Error] Could not get rate for {to}. Supported codes include USD, EUR, GBP, INR, JPY, CAD, AUD, etc."

        converted = rates[to]
        date = data.get("date", "today")
        unit_rate = converted / amount
        _CACHE[cache_key] = (unit_rate, date)

        return (
            f"{amount:,.2f} {frm} = {converted:,.4f} {to}\n"
            f"Exchange rate: 1 {frm} = {unit_rate:.6f} {to}\n"
            f"Rate date: {date}"
        )
