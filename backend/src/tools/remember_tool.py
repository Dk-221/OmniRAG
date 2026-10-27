"""
remember_tool – stores a user-provided fact into the ChromaDB 'memories' collection.

User facts are persisted with an embedding and can be recalled in future queries.
"""

from __future__ import annotations

import logging
from typing import Any

from src.tools._base import BaseTool

logger = logging.getLogger(__name__)


class RememberTool(BaseTool):
    """Store a key user fact or preference in persistent memory."""

    name = "remember"
    description = (
        "Store a fact, preference, or detail provided by the user into persistent memory. "
        "Use when the user explicitly asks to remember something or provides persistent context."
    )
    parameters = {
        "type": "object",
        "properties": {
            "fact": {
                "type": "string",
                "description": "The specific fact or detail to store in memory.",
            }
        },
        "required": ["fact"],
    }
    category = "knowledge"

    def run(self, fact: str, **_: Any) -> str:  # type: ignore[override]
        """Store *fact* into the memories collection."""
        from src.rag import add_memory

        fact = fact.strip()
        if not fact:
            return "[Error] Fact cannot be empty."

        try:
            mem = add_memory(fact)
            return f"Successfully remembered: '{fact}' (ID: {mem['id']})"
        except Exception as exc:
            logger.exception("Failed to store memory: %s", exc)
            return f"[Tool error] remember: {exc}"
