"""
knowledge_base_tool – searches the local ChromaDB vector store.

Use this tool when the user asks about content from uploaded documents,
PDFs, reports, manuals, or persistent memories.
Returns the top relevant passages with source filename and page number.
"""

from __future__ import annotations

from typing import Any

from src.tools._base import BaseTool
from src.rag import retrieve


class KnowledgeBaseTool(BaseTool):
    """Search the ingested document knowledge base and saved memories."""

    name = "search_knowledge_base"
    description = (
        "Search the local knowledge base of uploaded PDF/text documents and stored memories. "
        "Returns the most relevant text passages with filename and page numbers."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to look up in the knowledge base.",
            }
        },
        "required": ["query"],
    }
    category = "knowledge"

    def run(self, query: str, **_: Any) -> str:  # type: ignore[override]
        """Return top chunks matching *query*, with source metadata."""
        results = retrieve(query)
        if not results:
            return "No relevant documents found in the knowledge base."

        lines = []
        for i, r in enumerate(results, start=1):
            lines.append(
                f"[{i}] File: {r['filename']} | Page: {r['page']} | "
                f"Score: {r['score']}\n{r['text']}"
            )
        return "\n\n---\n\n".join(lines)
