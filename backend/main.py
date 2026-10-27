"""
main.py – FastAPI application for Agentic RAG with Real-Time Tools.

Run the server:
    uvicorn main:app --reload --port 8000

Run from CLI (single question):
    python main.py "What is the weather in London?"
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
import sys
from typing import AsyncGenerator, List, Optional

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

# ── ensure backend/ is on sys.path when running as `python main.py` ───────
_BACKEND_DIR = Path(__file__).resolve().parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from src.agent import run_agent_streaming
from src.config import settings
import src.rag as rag
from src.tool_registry import TOOLS

logger = logging.getLogger(__name__)


# ── lifespan: startup and cleanup ─────────────────────────────────────────
@asynccontextmanager
async def lifespan(app_: FastAPI):
    """Run startup logic (ingest KB, ensure directories); cleanup on shutdown."""
    logger.info("Starting up OmniRag backend…")
    settings.datasets_path.mkdir(parents=True, exist_ok=True)
    settings.knowledge_base_path.mkdir(parents=True, exist_ok=True)
    settings.chroma_path.mkdir(parents=True, exist_ok=True)

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, rag.ingest_directory)
    new_chunks = sum(v for v in results.values() if v > 0)
    logger.info(
        "Startup ingest complete. Files processed: %d, new chunks: %d",
        len(results),
        new_chunks,
    )
    yield


# ── FastAPI app ────────────────────────────────────────────────────────────
app = FastAPI(
    title="OmniRag Agent API",
    description="LLM agent with RAG, memories, dynamic tool routing, and real-time execution",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic models ────────────────────────────────────────────────────────
class HistoryMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: List[HistoryMessage] = []


# ── SSE generator helper ──────────────────────────────────────────────────
async def _sse_generator(
    user_message: str,
    history: List[dict],
) -> AsyncGenerator[str, None]:
    """Iterate over the agent stream and format as SSE messages."""
    try:
        async for event in run_agent_streaming(user_message, history):
            yield f"data: {json.dumps(event)}\n\n"
    except Exception as exc:
        logger.exception("Agent execution error in SSE generator: %s", exc)
        yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"


# ── routes: Health & Tools ────────────────────────────────────────────────
@app.get("/api/health")
async def health() -> JSONResponse:
    """Return server health and key configuration info."""
    return JSONResponse({
        "status": "ok" if settings.has_groq_key else "degraded",
        "provider": "groq",
        "model": settings.groq_model,
        "fallback_model": settings.groq_fallback_model,
        "documents_indexed": rag.total_chunks(),
        "api_key_configured": settings.has_groq_key,
        "verify_answers": settings.verify_answers,
        "router_max_tools": settings.router_max_tools,
        "message": (
            None if settings.has_groq_key
            else "GROQ_API_KEY is not set. Add it to backend/.env and restart."
        ),
    })


@app.get("/api/tools")
async def get_tools() -> JSONResponse:
    """List all registered agent tools with name, description, and category."""
    return JSONResponse([
        {
            "name": t.name,
            "description": t.description,
            "category": getattr(t, "category", "utility"),
        }
        for t in TOOLS
    ])


# ── routes: Chat ──────────────────────────────────────────────────────────
@app.post("/api/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    """
    Main chat endpoint – returns an SSE event stream.
    Events: plan, plan_step, thinking, tool_call, tool_result, artifact, verification, token, sources, done, error
    """
    if not settings.has_groq_key:
        async def _err():
            msg = (
                '{"type":"error","message":"GROQ_API_KEY is not configured. '
                'Add it to backend/.env and restart the server."}\n\n'
            )
            yield f"data: {msg}"
        return StreamingResponse(_err(), media_type="text/event-stream")

    history = [h.model_dump() for h in request.history]

    return StreamingResponse(
        _sse_generator(request.message, history),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── routes: Knowledge Base Documents ──────────────────────────────────────
@app.post("/api/ingest")
async def ingest() -> JSONResponse:
    """Re-index all files in the knowledge base directory."""
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, rag.ingest_directory)
    total_new = sum(v for v in results.values() if v > 0)
    return JSONResponse({
        "documents": len(results),
        "chunks": total_new,
        "details": results,
    })


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)) -> JSONResponse:
    """Upload a PDF, TXT, or MD file to the knowledge base and ingest it."""
    allowed = {".pdf", ".txt", ".md"}
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {sorted(allowed)}",
        )

    dest = settings.knowledge_base_path / (file.filename or "upload")
    content = await file.read()
    dest.write_bytes(content)
    logger.info("Uploaded knowledge doc: %s (%d bytes)", dest.name, len(content))

    loop = asyncio.get_event_loop()
    chunks = await loop.run_in_executor(None, rag.ingest_file, dest, True)

    return JSONResponse({"filename": dest.name, "chunks": chunks})


@app.get("/api/documents")
async def list_documents() -> JSONResponse:
    """List all indexed documents with chunk counts."""
    return JSONResponse(rag.list_documents())


@app.get("/api/documents/{filename}/page/{n}")
async def get_document_page(filename: str, n: int) -> JSONResponse:
    """Return the raw extracted text of page n of an indexed document for the source viewer."""
    res = rag.get_document_page(filename, n)
    if res is None:
        raise HTTPException(
            status_code=404,
            detail=f"Document '{filename}' was not found.",
        )
    text, total_pages = res
    return JSONResponse({
        "filename": filename,
        "page": min(n, total_pages),
        "total_pages": total_pages,
        "text": text,
    })


# ── routes: Datasets for Data Analysis ────────────────────────────────────
@app.post("/api/data/upload")
async def upload_dataset(file: UploadFile = File(...)) -> JSONResponse:
    """Upload a CSV or XLSX file for data analysis."""
    allowed = {".csv", ".xlsx", ".xls"}
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported dataset format '{suffix}'. Allowed: {sorted(allowed)}",
        )

    settings.datasets_path.mkdir(parents=True, exist_ok=True)
    dest = settings.datasets_path / (file.filename or "dataset.csv")
    content = await file.read()
    dest.write_bytes(content)
    logger.info("Uploaded dataset: %s (%d bytes)", dest.name, len(content))

    return JSONResponse({
        "filename": dest.name,
        "size_bytes": len(content),
        "message": f"Dataset '{dest.name}' uploaded successfully to data/datasets/.",
    })


@app.get("/api/data/files")
async def list_datasets() -> JSONResponse:
    """List all datasets available for analysis."""
    from src.tools.analyze_data_tool import list_datasets as get_ds
    return JSONResponse(get_ds())


# ── routes: Memories ──────────────────────────────────────────────────────
@app.get("/api/memories")
async def get_memories() -> JSONResponse:
    """List all stored user memories and facts."""
    return JSONResponse(rag.list_memories())


@app.delete("/api/memories/{memory_id}")
async def remove_memory(memory_id: str) -> JSONResponse:
    """Delete a stored memory by ID."""
    success = rag.delete_memory(memory_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Memory '{memory_id}' not found.")
    return JSONResponse({"success": True, "id": memory_id})


# ── CLI entry point ────────────────────────────────────────────────────────
async def _cli_async(question: str) -> None:
    print(f"\n🤖  Question: {question}\n{'─' * 60}")
    async for event in run_agent_streaming(question):
        t = event.get("type")
        if t == "plan":
            print("📋  Plan:")
            for s in event.get("steps", []):
                print(f"   [{s['id']}] {s['text']}")
        elif t == "plan_step":
            status_icon = "⏳" if event.get("status") == "running" else "✅"
            print(f"   {status_icon} Step {event.get('id')}: {event.get('status')}")
        elif t == "thinking":
            print(f"💭  {event['text']}")
        elif t == "tool_call":
            print(f"🔧  Tool call: {event['name']}({json.dumps(event['args'])})")
        elif t == "artifact":
            print(f"📦  Artifact [{event['kind']}]: {json.dumps(event['data'])[:100]}…")
        elif t == "tool_result":
            status = "✅" if event.get("ok") else "❌"
            art = f" [artifact: {event['artifact_ref']}]" if event.get("artifact_ref") else ""
            print(f"{status}  {event['name']}: {event['summary']}{art}")
        elif t == "verification":
            print(f"🛡️  Verification [{event['verdict'].upper()}]: {event.get('notes')}")
        elif t == "token":
            print(event["text"], end="", flush=True)
        elif t == "sources":
            print(f"\n\n📚  Sources:")
            for s in event.get("items", []):
                pg = f" (p. {s['page']})" if "page" in s else ""
                print(f"   [{s['type'].upper()}] {s['title']}{pg}")
        elif t == "done":
            print("\n" + "─" * 60)
        elif t == "error":
            print(f"\n❌  Error: {event['message']}")


def _cli_run(question: str) -> None:
    asyncio.run(_cli_async(question))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        _cli_run(" ".join(sys.argv[1:]))
    else:
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level=settings.log_level.lower(),
        )
