"""
Base class and shared helpers for all agent tools.

Every tool must subclass BaseTool and implement:
    - name (str)
    - description (str)
    - parameters (dict)  – JSON-Schema object
    - run(**kwargs)      – the actual logic; returns a plain string (or (str, artifact_dict))
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# Maximum characters returned to the LLM from any single tool call.
TOOL_RESULT_MAX_CHARS = 800


def truncate(text: str, max_chars: int = TOOL_RESULT_MAX_CHARS) -> str:
    """Truncate *text* to *max_chars* characters, appending '…' when cut."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + " …[truncated]"


class BaseTool(ABC):
    """Abstract base for all agent tools."""

    name: str
    description: str
    parameters: dict  # JSON-Schema "object" with a "properties" key
    category: str = "utility"  # one of: knowledge, web, finance, data, code, utility
    _last_artifact: Optional[Dict[str, Any]] = None

    @abstractmethod
    def run(self, **kwargs: Any) -> Union[str, Tuple[str, Dict[str, Any]]]:
        """Execute the tool and return a plain-string result (or tuple with artifact)."""

    def to_groq_spec(self) -> dict:
        """Return the Groq-compatible tool specification dict."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def safe_run(self, **kwargs: Any) -> str:
        """Run the tool safely, catching all exceptions so the agent loop never crashes."""
        try:
            res = self.run(**kwargs)
            if isinstance(res, tuple) and len(res) == 2 and isinstance(res[1], dict):
                self._last_artifact = res[1]
                res = res[0]
            return truncate(str(res))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Tool %s raised an error: %s", self.name, exc)
            return f"[Tool error] {self.name}: {exc}"

    def get_artifact(self) -> Optional[Dict[str, Any]]:
        """Retrieve and clear any artifact generated during the last safe_run."""
        art = getattr(self, "_last_artifact", None)
        self._last_artifact = None
        return art
