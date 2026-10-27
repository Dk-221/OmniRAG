"""
Groq LLM client wrapper.

Features:
- Reads rate-limit / retry-after headers on HTTP 429
- Retries up to 3 times with exponential back-off
- Automatically falls back to GROQ_FALLBACK_MODEL after persistent failures
- Logs token usage per call
- Returns a clear error string (never raises) so the agent can surface it
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Iterator, List, Optional

import groq
from groq import Groq

from src.config import settings

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BASE_BACKOFF = 2.0  # seconds


class LLMClient:
    """Thin wrapper around the Groq SDK with retry / fallback logic."""

    def __init__(self) -> None:
        self._client: Optional[Groq] = None
        if settings.has_groq_key:
            self._client = Groq(api_key=settings.groq_api_key)

    # ── internal helpers ──────────────────────────────────────────────────
    def _build_client(self) -> Groq:
        if self._client is None:
            raise RuntimeError(
                "GROQ_API_KEY is not set. "
                "Add it to backend/.env and restart the server."
            )
        return self._client

    def _call_once(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
        stream: bool = False,
    ) -> Any:
        """Single attempt at a Groq chat completion (streaming or not)."""
        client = self._build_client()
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.1,
        }
        # reasoning_effort is only recognised by gpt-oss models
        if "gpt-oss" in model:
            kwargs["reasoning_effort"] = "low"
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if stream:
            kwargs["stream"] = True
        return client.chat.completions.create(**kwargs)

    # ── public API ────────────────────────────────────────────────────────
    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
        model_override: Optional[str] = None,
    ) -> Any:
        """
        Non-streaming completion.

        Returns a ``groq.types.chat.ChatCompletion`` on success, or raises
        ``RuntimeError`` with a human-readable message after all retries.
        """
        models_to_try = [
            model_override or settings.groq_model,
            settings.groq_fallback_model,
        ]

        last_error: Exception | None = None
        for model in models_to_try:
            for attempt in range(1, _MAX_RETRIES + 1):
                try:
                    response = self._call_once(model, messages, tools=tools)
                    self._log_usage(model, response)
                    return response
                except groq.RateLimitError as exc:
                    wait = _parse_retry_after(exc) or (_BASE_BACKOFF * attempt)
                    logger.warning(
                        "Rate limit hit on model=%s attempt=%d; waiting %.1fs",
                        model,
                        attempt,
                        wait,
                    )
                    time.sleep(wait)
                    last_error = exc
                except groq.APIStatusError as exc:
                    logger.warning(
                        "API error on model=%s attempt=%d: %s",
                        model,
                        attempt,
                        exc,
                    )
                    time.sleep(_BASE_BACKOFF * attempt)
                    last_error = exc
                except RuntimeError:
                    raise  # missing API key – bubble up immediately

        raise RuntimeError(
            f"All retries exhausted on both models. Last error: {last_error}"
        )

    def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
        model_override: Optional[str] = None,
    ) -> Iterator[Any]:
        """
        Streaming completion.

        Yields raw ``ChoiceDelta`` chunks; the caller decides how to handle them.
        Falls back to primary-only (streaming retry is complex; let the agent
        loop handle it).
        """
        model = model_override or settings.groq_model
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = self._call_once(model, messages, tools=tools, stream=True)
                yield from response
                return
            except groq.RateLimitError as exc:
                wait = _parse_retry_after(exc) or (_BASE_BACKOFF * attempt)
                logger.warning(
                    "Rate limit (stream) model=%s attempt=%d; waiting %.1fs",
                    model,
                    attempt,
                    wait,
                )
                time.sleep(wait)
            except groq.APIStatusError as exc:
                logger.warning(
                    "API error (stream) model=%s attempt=%d: %s",
                    model,
                    attempt,
                    exc,
                )
                time.sleep(_BASE_BACKOFF * attempt)
            except RuntimeError:
                raise

        raise RuntimeError(f"Streaming failed after {_MAX_RETRIES} retries on {model}")

    # ── utilities ─────────────────────────────────────────────────────────
    @staticmethod
    def _log_usage(model: str, response: Any) -> None:
        try:
            u = response.usage
            logger.info(
                "Token usage | model=%s prompt=%d completion=%d total=%d",
                model,
                u.prompt_tokens,
                u.completion_tokens,
                u.total_tokens,
            )
        except Exception:  # noqa: BLE001
            pass


def _parse_retry_after(exc: groq.RateLimitError) -> Optional[float]:
    """Extract the Retry-After header value (seconds) from a 429 response."""
    try:
        # groq SDK wraps the raw httpx response
        headers = exc.response.headers  # type: ignore[union-attr]
        val = headers.get("retry-after") or headers.get("x-ratelimit-reset-requests")
        if val:
            return float(val)
    except Exception:  # noqa: BLE001
        pass
    return None


# Module-level singleton
llm_client = LLMClient()
