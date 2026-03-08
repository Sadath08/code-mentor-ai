"""
services/rag_service.py
-----------------------
Retrieval-Augmented Generation pipeline using FAISS + OpenAI embeddings.

Architecture:
  - FAISS IndexFlatIP  (inner product = cosine similarity on L2-normalized vectors)
  - L2-normalised query vectors for correct cosine similarity
  - Cosine similarity threshold filters out irrelevant chunks
  - Static fallback context when index is not built yet
  - Hot-reload support via reload_faiss_index()
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Module-level singletons ────────────────────────────────────────────────────
_faiss_index = None          # faiss.IndexFlatIP instance or None
_metadata: list[dict] = []  # parallel list of chunk dicts
_rag_mode: str = "fallback"  # "live" | "fallback"

# Cosine similarity floor — chunks below this score are dropped
_SCORE_THRESHOLD: float = 0.10


# ─────────────────────────────────────────────────────────────────────────────
# Index Loading / Hot-Reload
# ─────────────────────────────────────────────────────────────────────────────

def load_faiss_index() -> bool:
    """
    Load FAISS index + metadata from disk into memory.
    Called at app startup. Returns True on success.
    """
    global _faiss_index, _metadata, _rag_mode

    index_path = Path(settings.faiss_index_path)
    meta_path = index_path.parent / "metadata.json"

    if not index_path.exists():
        logger.warning(
            "FAISS index not found at %s — using static fallback context. "
            "Build it: cd backend && python knowledge_base/build_kb.py",
            index_path,
        )
        _metadata = _static_fallback_chunks()
        _rag_mode = "fallback"
        return False

    try:
        import faiss
        _faiss_index = faiss.read_index(str(index_path))
        if meta_path.exists():
            with open(meta_path, encoding="utf-8") as f:
                _metadata = json.load(f)
        _rag_mode = "live"
        logger.info("✅ FAISS index loaded: %d vectors | type=%s",
                    _faiss_index.ntotal, type(_faiss_index).__name__)
        return True
    except Exception as e:
        logger.error("Failed to load FAISS index: %s", e)
        _metadata = _static_fallback_chunks()
        _rag_mode = "fallback"
        return False


def reload_faiss_index() -> bool:
    """Hot-reload the FAISS index from disk without restarting the server."""
    logger.info("Hot-reloading FAISS index...")
    return load_faiss_index()


def get_rag_status() -> dict:
    """Return current RAG index state for health/debug API."""
    return {
        "mode": _rag_mode,
        "index_type": type(_faiss_index).__name__ if _faiss_index else "none",
        "vectors": int(_faiss_index.ntotal) if _faiss_index else 0,
        "metadata_count": len(_metadata),
        "score_threshold": _SCORE_THRESHOLD,
        "index_path": str(Path(settings.faiss_index_path).resolve()),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Core Retrieval
# ─────────────────────────────────────────────────────────────────────────────

async def retrieve_context(
    query: str,
    language: str = "python",
    top_k: int = 4,
) -> str:
    """
    Embed the query, search FAISS, filter by similarity + language, and return
    the top-k chunks joined as a context string for the LLM prompt.

    Falls back to static context if the FAISS index is unavailable.
    """
    if _faiss_index is None:
        return _fallback_context(language)

    try:
        vector = await _embed(query)
        # L2-normalise so that IndexFlatIP returns cosine similarity
        vec_norm = _l2_normalize(np.array([vector], dtype=np.float32))

        k = min(top_k * 3, _faiss_index.ntotal)
        scores, indices = _faiss_index.search(vec_norm, k)

        chunks: list[str] = []
        seen: set[str] = set()

        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(_metadata):
                continue
            if float(score) < _SCORE_THRESHOLD:
                continue

            chunk = _metadata[idx]
            chunk_lang = chunk.get("language", "general")
            if chunk_lang not in ("general", language.lower()):
                continue

            text = chunk.get("text", "").strip()
            if not text:
                continue

            dedup_key = f"{chunk.get('source', '')}:{chunk.get('concept', '')}"
            if dedup_key in seen and chunk.get("source"):
                continue
            seen.add(dedup_key)

            chunks.append(text)
            if len(chunks) >= top_k:
                break

        if not chunks:
            logger.debug("No chunks passed threshold %.2f — using fallback", _SCORE_THRESHOLD)
            return _fallback_context(language)

        logger.debug("Retrieved %d RAG chunks for language=%s", len(chunks), language)
        return "\n\n---\n\n".join(chunks)

    except Exception as e:
        logger.error("RAG retrieval failed: %s", e, exc_info=True)
        return _fallback_context(language)


async def retrieve_context_with_sources(
    query: str,
    language: str = "general",
    top_k: int = 4,
) -> dict:
    """Like retrieve_context() but also returns source chunk metadata."""
    if _faiss_index is None:
        return {"context": _fallback_context(language), "source_chunks": [], "mode": _rag_mode}

    try:
        vector = await _embed(query)
        vec_norm = _l2_normalize(np.array([vector], dtype=np.float32))
        k = min(top_k * 3, _faiss_index.ntotal)
        scores, indices = _faiss_index.search(vec_norm, k)

        result_chunks: list[dict] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(_metadata):
                continue
            if float(score) < _SCORE_THRESHOLD:
                continue
            chunk = _metadata[idx]
            chunk_lang = chunk.get("language", "general")
            if chunk_lang not in ("general", language.lower()):
                continue
            text = chunk.get("text", "").strip()
            if not text:
                continue
            result_chunks.append({
                "text": text,
                "score": round(float(score), 4),
                "language": chunk_lang,
                "concept": chunk.get("concept", "general"),
                "source": chunk.get("source", "knowledge_base"),
            })
            if len(result_chunks) >= top_k:
                break

        context = "\n\n---\n\n".join(c["text"] for c in result_chunks) or _fallback_context(language)
        return {"context": context, "source_chunks": result_chunks, "mode": _rag_mode}

    except Exception as e:
        logger.error("RAG retrieval with sources failed: %s", e, exc_info=True)
        return {"context": _fallback_context(language), "source_chunks": [], "mode": "error"}


# ─────────────────────────────────────────────────────────────────────────────
# Embedding Helper
# ─────────────────────────────────────────────────────────────────────────────

async def _embed(text: str) -> list[float]:
    """
    Generate embedding via OpenAI text-embedding-3-small.
    Runs in a thread so it doesn't block the event loop.
    """
    import asyncio
    from openai import OpenAI

    # Use OPENAI_API_KEY from env (load_dotenv() called in main.py)
    openai_key = os.getenv("OPENAI_API_KEY") or settings.openai_api_key
    client = OpenAI(api_key=openai_key)

    response = await asyncio.to_thread(
        client.embeddings.create,
        model="text-embedding-3-small",
        input=text[:8000],
    )
    return response.data[0].embedding


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    """L2-normalize each row of a 2D float32 matrix (required for cosine via IndexFlatIP)."""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return (matrix / norms).astype(np.float32)


# ─────────────────────────────────────────────────────────────────────────────
# Static Fallback Context
# ─────────────────────────────────────────────────────────────────────────────

def _fallback_context(language: str) -> str:
    chunks = _static_fallback_chunks()
    relevant = [c["text"] for c in chunks if c.get("language") in ("general", language.lower())]
    return "\n\n---\n\n".join(relevant[:4]) or "No context available."


def _static_fallback_chunks() -> list[dict]:
    """Minimal hardcoded knowledge base used when FAISS index is absent."""
    return [
        {
            "language": "python", "concept": "recursion",
            "text": (
                "PYTHON RECURSION BEST PRACTICES:\n"
                "• Always define a base case first to prevent infinite recursion.\n"
                "• Ensure every recursive call moves toward the base case.\n"
                "• Common mistake: missing return in the recursive branch.\n"
                "Example:\ndef factorial(n):\n    if n <= 1: return 1\n    return n * factorial(n - 1)"
            ),
        },
        {
            "language": "python", "concept": "loops",
            "text": (
                "PYTHON LOOP COMMON ERRORS:\n"
                "• Off-by-one: use range(len(arr)) not range(len(arr)+1).\n"
                "• Mutating a list while iterating causes skipped elements.\n"
                "• Prefer enumerate() over manual index tracking.\n"
                "• Infinite while loops: always ensure the condition eventually becomes False."
            ),
        },
        {
            "language": "general", "concept": "clean_code",
            "text": (
                "CLEAN CODE GUIDELINES:\n"
                "• Use descriptive variable names.\n"
                "• Single responsibility: each function should do one thing.\n"
                "• DRY principle: extract common logic.\n"
                "• Add docstrings to public functions."
            ),
        },
        {
            "language": "python", "concept": "syntax_error",
            "text": (
                "COMMON PYTHON ERRORS:\n"
                "• IndentationError: Python uses indentation for blocks.\n"
                "• NameError: referencing a variable before assignment.\n"
                "• TypeError: wrong type (e.g. str + int).\n"
                "• IndexError: accessing list index out of range."
            ),
        },
        {
            "language": "general", "concept": "algorithms",
            "text": (
                "ALGORITHMIC COMPLEXITY:\n"
                "• O(n²) nested loops are often optimizable with hashmaps to O(n).\n"
                "• Two-pointer technique eliminates one nested loop in sorted arrays.\n"
                "• Binary search: O(log n) on sorted arrays."
            ),
        },
        {
            "language": "javascript", "concept": "async_await",
            "text": (
                "JAVASCRIPT ASYNC/AWAIT:\n"
                "• async functions always return a Promise.\n"
                "• Use await inside async functions; forgetting gives a Promise object.\n"
                "• Always wrap await in try/catch for error handling."
            ),
        },
        {
            "language": "java", "concept": "runtime_error",
            "text": (
                "JAVA NULLPOINTEREXCEPTION:\n"
                "• Check 'if (obj != null)' before calling methods.\n"
                "• Use Optional<T> for values that may be absent."
            ),
        },
    ]