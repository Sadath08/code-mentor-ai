"""
services/document_service.py
-----------------------------
Full RAG document ingestion pipeline.
Supports PDF, DOCX, TXT, Markdown, and plain code files.

Flow:
  1. Extract raw text from the uploaded file.
  2. Chunk into ~400-token segments (paragraph-aware) with 50-token overlap.
  3. Embed each chunk via OpenAI text-embedding-3-small.
  4. L2-normalize vectors (required for cosine similarity with IndexFlatIP).
  5. Tag each chunk with an inferred programming concept.
  6. Upsert new vectors into the live in-memory FAISS index.
  7. Persist updated index + metadata.json to disk.
  8. Return (chunk_count, status).
"""
from __future__ import annotations

import io
import json
import logging
import re
from pathlib import Path
from typing import List, Tuple

from app.config import get_settings
from rag import add_document_chunk
from app.database import SessionLocal

logger = logging.getLogger(__name__)
settings = get_settings()


# ─────────────────────────────────────────────────────────────────────────────
# Text Extraction
# ─────────────────────────────────────────────────────────────────────────────

def extract_text_from_pdf(data: bytes) -> str:
    """Extract all text from a PDF file (bytes)."""
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages)
    except ImportError:
        raise RuntimeError("pypdf is not installed. Run: pip install pypdf==4.2.0")
    except Exception as exc:
        logger.error("PDF extraction failed: %s", exc)
        raise


def extract_text_from_docx(data: bytes) -> str:
    """Extract all text from a DOCX file (bytes)."""
    try:
        from docx import Document
        doc = Document(io.BytesIO(data))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)
    except ImportError:
        raise RuntimeError("python-docx is not installed. Run: pip install python-docx==1.1.2")
    except Exception as exc:
        logger.error("DOCX extraction failed: %s", exc)
        raise


def extract_text(data: bytes, file_type: str) -> str:
    """Dispatch text extraction based on file type."""
    ft = file_type.lower().lstrip(".")
    if ft == "pdf":
        return extract_text_from_pdf(data)
    if ft in ("docx", "doc"):
        return extract_text_from_docx(data)
    # Plain text / markdown / code files
    return data.decode("utf-8", errors="replace")


# ─────────────────────────────────────────────────────────────────────────────
# Chunking (paragraph-aware with overlap)
# ─────────────────────────────────────────────────────────────────────────────

def _rough_token_count(text: str) -> int:
    """Rough token estimator (~4 chars per token)."""
    return len(text) // 4


def chunk_text(
    text: str,
    chunk_tokens: int = 400,
    overlap_tokens: int = 50,
) -> List[str]:
    """
    Split text into overlapping chunks of ~chunk_tokens tokens.
    Prefers paragraph boundaries (double newlines) over sentence splits,
    producing more semantically coherent chunks.
    """
    # Normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []

    # Split on paragraph boundaries first, then sentences within large paragraphs
    paragraphs = re.split(r"\n\n+", text)
    segments: list[str] = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if _rough_token_count(para) > chunk_tokens:
            # Large paragraph: split on sentence boundaries
            sentences = re.split(r"(?<=[.!?\n])\s+", para)
            segments.extend(s.strip() for s in sentences if s.strip())
        else:
            segments.append(para)

    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    overlap_chars = overlap_tokens * 4

    for segment in segments:
        s_tokens = _rough_token_count(segment)
        if current_tokens + s_tokens > chunk_tokens and current:
            full_chunk = "\n\n".join(current)
            chunks.append(full_chunk)
            # Keep overlap: take tail chars of the current chunk
            tail = full_chunk[-overlap_chars:]
            current = [tail]
            current_tokens = _rough_token_count(tail)
        current.append(segment)
        current_tokens += s_tokens

    if current:
        chunks.append("\n\n".join(current))

    return [c.strip() for c in chunks if c.strip()]


# ─────────────────────────────────────────────────────────────────────────────
# Concept Tagging
# ─────────────────────────────────────────────────────────────────────────────

# Keyword → concept mapping for auto-tagging uploaded documents
_CONCEPT_KEYWORDS: dict[str, list[str]] = {
    "recursion": ["recursion", "recursive", "base case", "factorial", "fibonacci"],
    "loops": ["for loop", "while loop", "enumerate", "iterate", "iteration", "range("],
    "arrays": ["array", "list", "index", "append", "slice", "pop("],
    "dictionaries": ["dictionary", "dict", "hashmap", "key", "value", ".get("],
    "sorting": ["sort", "sorted", "merge sort", "quicksort", "bubble sort"],
    "binary_search": ["binary search", "lo", "hi", "mid", "sorted array"],
    "dynamic_programming": ["dynamic programming", "memoization", "tabulation", "dp[", "subproblem"],
    "graphs": ["graph", "bfs", "dfs", "adjacency", "vertex", "edge", "neighbor"],
    "trees": ["tree", "binary tree", "bst", "root", "leaf", "traversal", "in-order"],
    "heaps": ["heap", "heapq", "priority queue", "heappush", "heappop"],
    "object_oriented_programming": ["class", "object", "inheritance", "encapsulation", "polymorphism"],
    "async_await": ["async", "await", "promise", "asyncio", "coroutine"],
    "runtime_error": ["null", "none", "exception", "error", "traceback", "undefined"],
    "system_design": ["cache", "load balancer", "database", "scalability", "microservice"],
    "performance": ["time complexity", "space complexity", "big o", "optimize", "efficient"],
}


def tag_concept(text: str) -> str:
    """
    Keyword-based concept tagger for uploaded document chunks.
    Returns the best-matching concept label, or 'general' if no match.
    """
    text_lower = text.lower()
    best_concept = "general"
    best_score = 0

    for concept, keywords in _CONCEPT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > best_score:
            best_score = score
            best_concept = concept

    return best_concept


# ─────────────────────────────────────────────────────────────────────────────
# DB Upsert
# ─────────────────────────────────────────────────────────────────────────────

def upsert_into_db(
    chunks: List[str],
    metadata_records: List[dict],
) -> int:
    """
    Add chunk vectors to the PostgreSQL database using rag.py functionality.
    Returns the number of chunks added.
    """
    
    db = SessionLocal()
    try:
        added = 0
        for i, chunk in enumerate(chunks):
            record = metadata_records[i]
            topic = record.get("concept", "general")
            source = record.get("source", "unknown")
            add_document_chunk(chunk, topic, source, i, db)
            added += 1
            
        logger.info("Inserted %d chunks into knowledge_base DB", added)
        return added
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Main Ingestion Entry Point
# ─────────────────────────────────────────────────────────────────────────────

async def ingest_document(
    data: bytes,
    filename: str,
    file_type: str,
    language: str = "general",
) -> Tuple[int, str]:
    """
    Full ingestion pipeline for an uploaded document.

    Args:
        data:      raw file bytes
        filename:  original filename (stored in metadata for provenance)
        file_type: 'pdf', 'docx', or 'text'
        language:  programming language tag for retrieval filtering

    Returns:
        (chunk_count, status)  where status is 'indexed' or 'error: <reason>'
    """
    try:
        # Step 1 – Extract text
        raw_text = extract_text(data, file_type)
        if not raw_text.strip():
            return 0, "error: empty document"

        # Step 2 – Paragraph-aware chunking
        chunks = chunk_text(raw_text)
        if not chunks:
            return 0, "error: no chunks produced"
        logger.info("Document '%s' → %d chunks", filename, len(chunks))

        # Step 3 – Build metadata records with concept tagging
        records = [
            {
                "text": chunk,
                "language": language,
                "source": filename,
                "concept": tag_concept(chunk),
            }
            for chunk in chunks
        ]

        # Step 4 – Upsert chunks into pgvector DB
        added = upsert_into_db(chunks, records)

        logger.info(
            "✅ Ingested '%s': %d chunks indexed (language=%s)",
            filename, added, language,
        )
        return added, "indexed"

    except Exception as exc:
        logger.error("Ingestion failed for '%s': %s", filename, exc, exc_info=True)
        return 0, f"error: {exc}"
