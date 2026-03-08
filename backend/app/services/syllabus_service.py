"""
services/syllabus_service.py
-----------------------------
Handles user-specific syllabus document storage and personal FAISS indexing.

Each user gets their own FAISS index stored at:
  knowledge_base/user_indexes/{user_id}/faiss.index
  knowledge_base/user_indexes/{user_id}/metadata.json

The global Knowledge Base index is NOT modified.
"""
from __future__ import annotations

import io
import json
import logging
import re
from pathlib import Path
from typing import List, Tuple

import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

USER_INDEX_ROOT = Path("knowledge_base/user_indexes")
CHUNK_SIZE = 400        # ~tokens per chunk
CHUNK_OVERLAP = 50


# ── Text extraction ───────────────────────────────────────────────────────────

def _extract_text(data: bytes, file_type: str) -> str:
    if file_type == "pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(data))
            return "\n\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            raise RuntimeError(f"PDF extraction failed: {e}")
    elif file_type == "docx":
        try:
            from docx import Document
            doc = Document(io.BytesIO(data))
            return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as e:
            raise RuntimeError(f"DOCX extraction failed: {e}")
    else:
        return data.decode("utf-8", errors="replace")


# ── Chunking ──────────────────────────────────────────────────────────────────

def _chunk_text(text: str, filename: str) -> List[dict]:
    paragraphs = re.split(r"\n{2,}", text.strip())
    chunks: List[dict] = []
    current = ""

    for para in paragraphs:
        words = para.split()
        if len(current.split()) + len(words) <= CHUNK_SIZE:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append({"content": current, "source": filename, "topic": "syllabus"})
            current = para

    if current:
        chunks.append({"content": current, "source": filename, "topic": "syllabus"})

    return chunks


# ── Embedding ─────────────────────────────────────────────────────────────────

def _embed_texts(texts: List[str]) -> np.ndarray:
    """Embed a list of texts using Gemini embedding API."""
    import google.generativeai as genai
    import warnings; warnings.filterwarnings("ignore")

    genai.configure(api_key=settings.gemini_api_key)
    vectors = []
    for text in texts:
        result = genai.embed_content(
            model=settings.embedding_model,
            content=text,
            task_type="retrieval_document",
        )
        vectors.append(result["embedding"])
    arr = np.array(vectors, dtype=np.float32)
    # L2-normalise for cosine similarity
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    return arr / norms


def _embed_query(text: str) -> np.ndarray:
    """Embed a single query string."""
    import google.generativeai as genai
    import warnings; warnings.filterwarnings("ignore")

    genai.configure(api_key=settings.gemini_api_key)
    result = genai.embed_content(
        model=settings.embedding_model,
        content=text,
        task_type="retrieval_query",
    )
    vec = np.array([result["embedding"]], dtype=np.float32)
    norms = np.linalg.norm(vec, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    return vec / norms


# ── Index I/O ─────────────────────────────────────────────────────────────────

def _user_dir(user_id: str) -> Path:
    d = USER_INDEX_ROOT / user_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_user_meta(user_id: str) -> List[dict]:
    meta_path = _user_dir(user_id) / "metadata.json"
    if meta_path.exists():
        with open(meta_path, encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_user_meta(user_id: str, metadata: List[dict]) -> None:
    meta_path = _user_dir(user_id) / "metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


# ── Public API ────────────────────────────────────────────────────────────────

def ingest_user_document(data: bytes, filename: str, file_type: str, user_id: str) -> Tuple[int, str]:
    """
    Extract, chunk, embed, and index a user-uploaded document into their
    personal FAISS index. Returns (chunk_count, status_string).
    """
    import faiss

    try:
        text = _extract_text(data, file_type)
    except Exception as e:
        return 0, f"extraction_failed: {e}"

    chunks = _chunk_text(text, filename)
    if not chunks:
        return 0, "no_content"

    try:
        vectors = _embed_texts([c["content"] for c in chunks])
    except Exception as e:
        logger.error("Embedding failed for user %s: %s", user_id, e)
        return 0, f"embedding_failed: {e}"

    user_dir = _user_dir(user_id)
    index_path = user_dir / "faiss.index"
    existing_meta = _load_user_meta(user_id)

    dim = vectors.shape[1]
    if index_path.exists():
        index = faiss.read_index(str(index_path))
    else:
        index = faiss.IndexFlatIP(dim)

    index.add(vectors)
    faiss.write_index(index, str(index_path))

    existing_meta.extend(chunks)
    _save_user_meta(user_id, existing_meta)

    logger.info("✅ User %s: indexed %d chunks from '%s'", user_id, len(chunks), filename)
    return len(chunks), "indexed"


def retrieve_user_context(question: str, user_id: str, k: int = 4) -> List[dict]:
    """
    Search the user's personal FAISS index for relevant chunks.
    Returns list of dicts: {content, source, topic, similarity}.
    """
    import faiss

    index_path = _user_dir(user_id) / "faiss.index"
    if not index_path.exists():
        return []

    meta = _load_user_meta(user_id)
    if not meta:
        return []

    try:
        index = faiss.read_index(str(index_path))
        query_vec = _embed_query(question)
        k = min(k, index.ntotal)
        scores, idxs = index.search(query_vec, k)
        results = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx < 0 or idx >= len(meta) or score < 0.05:
                continue
            chunk = dict(meta[idx])
            chunk["similarity"] = round(float(score), 4)
            results.append(chunk)
        return results
    except Exception as e:
        logger.error("User RAG retrieval failed for %s: %s", user_id, e)
        return []


def list_user_documents(user_id: str) -> List[str]:
    """Return list of unique filenames indexed for this user."""
    meta = _load_user_meta(user_id)
    return list(dict.fromkeys(c.get("source", "") for c in meta if c.get("source")))
