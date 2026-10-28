"""
RAG pipeline: ingest → chunk → embed → store → retrieve.

Uses:
- pypdf        for PDF parsing
- sentence-transformers (all-MiniLM-L6-v2) for LOCAL embeddings
- ChromaDB     for persistent vector storage (documents & memories)

File hashes are tracked in a JSON sidecar so unchanged files are never
re-embedded (saves time and avoids duplicate chunks).
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from src.config import settings

logger = logging.getLogger(__name__)

# ── constants ─────────────────────────────────────────────────────────────
_EMBED_MODEL = "all-MiniLM-L6-v2"
_COLLECTION = "knowledge_base"
_MEMORIES_COLLECTION = "memories"
_CHUNK_SIZE = 500   # tokens (approximate; split on whitespace)
_CHUNK_OVERLAP = 50
_TOP_K = 3
_HASH_FILE = settings.chroma_path / "file_hashes.json"


# ── lazy singletons ───────────────────────────────────────────────────────
_embedder: Optional[SentenceTransformer] = None
_chroma_client: Optional[chromadb.ClientAPI] = None
_collection: Optional[chromadb.Collection] = None
_mem_collection: Optional[chromadb.Collection] = None


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        logger.info("Loading sentence-transformers model: %s (CPU mode)", _EMBED_MODEL)
        try:
            import torch
            torch.set_num_threads(1)
        except Exception:
            pass
        _embedder = SentenceTransformer(_EMBED_MODEL, device="cpu")
    return _embedder


def _get_chroma_client() -> chromadb.ClientAPI:
    global _chroma_client
    if _chroma_client is None:
        settings.chroma_path.mkdir(parents=True, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(
            path=str(settings.chroma_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _chroma_client


def _get_collection() -> chromadb.Collection:
    global _collection
    if _collection is None:
        client = _get_chroma_client()
        _collection = client.get_or_create_collection(
            name=_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def _get_memories_collection() -> chromadb.Collection:
    global _mem_collection
    if _mem_collection is None:
        client = _get_chroma_client()
        _mem_collection = client.get_or_create_collection(
            name=_MEMORIES_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
    return _mem_collection


# ── hash tracking ─────────────────────────────────────────────────────────
def _load_hashes() -> Dict[str, str]:
    if _HASH_FILE.exists():
        try:
            return json.loads(_HASH_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_hashes(hashes: Dict[str, str]) -> None:
    _HASH_FILE.parent.mkdir(parents=True, exist_ok=True)
    _HASH_FILE.write_text(json.dumps(hashes, indent=2), encoding="utf-8")


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


# ── text extraction ───────────────────────────────────────────────────────
def _extract_text_from_pdf(path: Path) -> List[Tuple[str, int]]:
    """Return [(page_text, page_number), ...] from a PDF."""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append((text, i))
    return pages


def _extract_text_from_txt(path: Path) -> List[Tuple[str, int]]:
    """
    Split TXT/MD files into logical pages (approx 2000-2400 chars).
    Honors form-feeds (\f) or paragraph boundaries (\n\n).
    """
    try:
        full_text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        logger.error("Failed to read text file %s: %s", path.name, exc)
        return []

    # 1. Explicit form feeds if present
    if "\f" in full_text:
        pages = [p.strip() for p in full_text.split("\f") if p.strip()]
        if pages:
            return [(p, i + 1) for i, p in enumerate(pages)]

    # 2. Short files (<= 2200 chars) are single-page
    if len(full_text) <= 2200:
        return [(full_text, 1)]

    # 3. Split by paragraphs/sections (\n\n) into ~2200 char pages
    paragraphs = full_text.split("\n\n")
    pages: List[Tuple[str, int]] = []
    current_page: List[str] = []
    current_len = 0

    for p in paragraphs:
        p_len = len(p)
        if current_len + p_len > 2200 and current_page:
            page_text = "\n\n".join(current_page).strip()
            if page_text:
                pages.append((page_text, len(pages) + 1))
            current_page = [p]
            current_len = p_len
        else:
            current_page.append(p)
            current_len += p_len + 2

    if current_page:
        page_text = "\n\n".join(current_page).strip()
        if page_text:
            pages.append((page_text, len(pages) + 1))

    return pages if pages else [(full_text, 1)]


def _extract_text(path: Path) -> List[Tuple[str, int]]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_text_from_pdf(path)
    if suffix in {".txt", ".md"}:
        return _extract_text_from_txt(path)
    logger.warning("Unsupported file type: %s – skipping", path.name)
    return []


def get_document_page(filename: str, page: int) -> Optional[Tuple[str, int]]:
    """Return (text, total_pages) for *page* (1-indexed) of *filename*, with safe clamping."""
    file_path = settings.knowledge_base_path / filename
    if not file_path.exists():
        return None

    pages = _extract_text(file_path)
    if not pages:
        return None

    total_pages = len(pages)
    target_page = max(1, min(page, total_pages))

    for text, p_num in pages:
        if p_num == target_page:
            return text, total_pages

    return pages[0][0], total_pages


# ── chunking ──────────────────────────────────────────────────────────────
def _chunk_text(text: str, chunk_size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP) -> List[str]:
    words = text.split()
    chunks: List[str] = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end == len(words):
            break
        start += chunk_size - overlap
    return chunks


# ── ingestion ─────────────────────────────────────────────────────────────
def ingest_file(path: Path, force: bool = False) -> int:
    hashes = _load_hashes()
    current_hash = _file_hash(path)

    if not force and hashes.get(str(path)) == current_hash:
        logger.debug("Skipping unchanged file: %s", path.name)
        return 0

    logger.info("Ingesting: %s", path.name)
    pages = _extract_text(path)
    if not pages:
        return 0

    collection = _get_collection()
    embedder = _get_embedder()

    try:
        existing = collection.get(where={"filename": path.name})
        if existing["ids"]:
            collection.delete(ids=existing["ids"])
            logger.debug("Deleted %d old chunks for %s", len(existing["ids"]), path.name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not delete old chunks for %s: %s", path.name, exc)

    all_chunks: List[str] = []
    all_ids: List[str] = []
    all_meta: List[Dict[str, Any]] = []

    for page_text, page_num in pages:
        for chunk_idx, chunk in enumerate(_chunk_text(page_text)):
            chunk_id = f"{path.stem}_p{page_num}_c{chunk_idx}"
            all_chunks.append(chunk)
            all_ids.append(chunk_id)
            all_meta.append({
                "filename": path.name,
                "page": page_num,
                "chunk": chunk_idx,
            })

    if not all_chunks:
        return 0

    embeddings = embedder.encode(
        all_chunks, batch_size=16, show_progress_bar=False
    ).tolist()
    collection.add(
        ids=all_ids,
        documents=all_chunks,
        embeddings=embeddings,
        metadatas=all_meta,
    )

    hashes[str(path)] = current_hash
    _save_hashes(hashes)
    logger.info("Added %d chunks from %s", len(all_chunks), path.name)
    return len(all_chunks)


def ingest_directory(directory: Optional[Path] = None) -> Dict[str, int]:
    directory = directory or settings.knowledge_base_path
    directory.mkdir(parents=True, exist_ok=True)
    results: Dict[str, int] = {}
    for ext in ("*.pdf", "*.txt", "*.md"):
        for fpath in directory.glob(ext):
            try:
                n = ingest_file(fpath)
                results[fpath.name] = n
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to ingest %s: %s", fpath.name, exc)
                results[fpath.name] = -1
    import gc
    gc.collect()
    return results


# ── memory management ─────────────────────────────────────────────────────
def add_memory(fact: str) -> Dict[str, Any]:
    """Store a fact into the 'memories' Chroma collection."""
    mem_coll = _get_memories_collection()
    embedder = _get_embedder()

    mem_id = str(uuid.uuid4())
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    embedding = embedder.encode([fact], show_progress_bar=False).tolist()[0]

    mem_coll.add(
        ids=[mem_id],
        documents=[fact],
        embeddings=[embedding],
        metadatas=[{"created_at": timestamp}],
    )
    logger.info("Stored memory [%s]: %s", mem_id, fact)
    return {"id": mem_id, "fact": fact, "created_at": timestamp}


def list_memories() -> List[Dict[str, Any]]:
    """List all stored memories."""
    mem_coll = _get_memories_collection()
    if mem_coll.count() == 0:
        return []

    data = mem_coll.get(include=["documents", "metadatas"])
    items = []
    for mid, doc, meta in zip(data["ids"], data["documents"], data["metadatas"]):
        items.append({
            "id": mid,
            "fact": doc,
            "created_at": meta.get("created_at") if meta else None,
        })
    return items


def delete_memory(memory_id: str) -> bool:
    """Delete a memory by ID."""
    mem_coll = _get_memories_collection()
    try:
        mem_coll.delete(ids=[memory_id])
        logger.info("Deleted memory [%s]", memory_id)
        return True
    except Exception as exc:
        logger.warning("Failed to delete memory [%s]: %s", memory_id, exc)
        return False


def retrieve_memories(query: str, top_k: int = 2) -> List[Dict[str, Any]]:
    """Retrieve top-*k* memories most relevant to query."""
    mem_coll = _get_memories_collection()
    if mem_coll.count() == 0:
        return []

    embedder = _get_embedder()
    q_embedding = embedder.encode([query], show_progress_bar=False).tolist()[0]
    n_res = min(top_k, mem_coll.count())
    res = mem_coll.query(
        query_embeddings=[q_embedding],
        n_results=n_res,
        include=["documents", "metadatas", "distances"],
    )

    items = []
    if res["documents"] and res["documents"][0]:
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            items.append({
                "text": f"Memory: {doc}",
                "filename": "[Memory]",
                "page": 1,
                "score": round(1 - dist, 4),
            })
    return items


# ── retrieval ─────────────────────────────────────────────────────────────
def retrieve(query: str, top_k: int = _TOP_K) -> List[Dict[str, Any]]:
    """
    Retrieve top-*k* items from documents, plus relevant facts from memories.
    """
    collection = _get_collection()
    embedder = _get_embedder()

    items: List[Dict[str, Any]] = []

    # Check memories collection as well
    memory_items = retrieve_memories(query, top_k=2)
    items.extend(memory_items)

    if collection.count() > 0:
        q_embedding = embedder.encode([query], show_progress_bar=False).tolist()[0]
        results = collection.query(
            query_embeddings=[q_embedding],
            n_results=min(top_k, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            items.append({
                "text": doc,
                "filename": meta.get("filename", "unknown"),
                "page": meta.get("page", 1),
                "score": round(1 - dist, 4),
            })

    # Sort combined by score descending
    items.sort(key=lambda x: x["score"], reverse=True)
    return items[:top_k + len(memory_items)]


# ── document listing ──────────────────────────────────────────────────────
def list_documents() -> List[Dict[str, Any]]:
    """Return [{filename, chunks}] for every document in the vector store."""
    collection = _get_collection()
    if collection.count() == 0:
        return []

    all_meta = collection.get(include=["metadatas"])["metadatas"]
    counts: Dict[str, int] = {}
    for m in all_meta:
        fname = m.get("filename", "unknown")
        counts[fname] = counts.get(fname, 0) + 1

    return [{"filename": k, "chunks": v} for k, v in sorted(counts.items())]


def total_chunks() -> int:
    """Total number of chunks currently stored in document knowledge base."""
    return _get_collection().count()
