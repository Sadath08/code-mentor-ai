"""
rag.py
------
Retrieval-Augmented Generation pipeline using google-generativeai and FAISS.

Two FAISS indices:
  • _kb_index  : global knowledge base (built by build_kb.py)  — faiss_index_path
  • _user_index: user-uploaded documents                        — user_faiss_index_path

search_knowledge_base() → uses the GLOBAL KB index (for code analysis)
add_document_chunk()    → writes into the USER document index
"""
from __future__ import annotations
import logging
import os
import re
import time
from typing import List

import faiss
import numpy as np
from sqlalchemy.orm import Session
import google.generativeai as genai

from app.models.knowledge_base import KnowledgeBase
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

genai.configure(api_key=settings.gemini_api_key)

DIMENSIONS = 768          # models/embedding-001 dimension
SIM_THRESHOLD = 0.15      # minimum cosine-similarity to include a chunk (lowered from 0.30)

# ── Two separate FAISS index singletons ──────────────────────────
_kb_index   = None   # global knowledge base (faiss_index_path)
_user_index = None   # user uploaded docs  (user_faiss_index_path)


# ─────────────────────────────────────────────────────────────────
# Index management: GLOBAL KB index
# ─────────────────────────────────────────────────────────────────

def get_kb_faiss_index() -> faiss.IndexIDMap:
    """Load or initialise the GLOBAL knowledge-base FAISS index."""
    global _kb_index
    if _kb_index is not None:
        return _kb_index

    index_path = settings.faiss_index_path
    if os.path.exists(index_path):
        try:
            _kb_index = faiss.read_index(index_path)
            logger.info(
                "✅ Loaded GLOBAL KB FAISS index from %s with %d vectors.",
                index_path, _kb_index.ntotal,
            )
        except Exception as e:
            logger.error("Failed to load global FAISS index: %s", e)
            _kb_index = _make_flat_index()
    else:
        logger.warning(
            "Global FAISS index not found at %s. "
            "Run knowledge_base/build_kb.py to create it.",
            index_path,
        )
        _kb_index = _make_flat_index()

    if _kb_index.ntotal == 0:
        logger.warning(
            "⚠️  FAISS index is EMPTY — run build_kb.py to populate the knowledge base. "
            "Code analysis will still work but without RAG context."
        )
    return _kb_index


# ─────────────────────────────────────────────────────────────────
# Index management: USER document index
# ─────────────────────────────────────────────────────────────────

def get_user_faiss_index() -> faiss.IndexIDMap:
    """Load or initialise the USER-document FAISS index."""
    global _user_index
    if _user_index is not None:
        return _user_index

    index_path = settings.user_faiss_index_path
    if os.path.exists(index_path):
        try:
            _user_index = faiss.read_index(index_path)
            logger.info(
                "✅ Loaded USER FAISS index from %s with %d vectors.",
                index_path, _user_index.ntotal,
            )
        except Exception as e:
            logger.error("Failed to load USER FAISS index: %s", e)
            _user_index = _make_flat_index()
    else:
        _user_index = _make_flat_index()

    return _user_index

# backward-compat alias used by main.py startup hook
def get_faiss_index() -> faiss.IndexIDMap:
    return get_kb_faiss_index()


def _make_flat_index() -> faiss.IndexIDMap:
    base = faiss.IndexFlatIP(DIMENSIONS)
    return faiss.IndexIDMap(base)


def save_user_faiss_index():
    if _user_index is not None:
        os.makedirs(os.path.dirname(settings.user_faiss_index_path), exist_ok=True)
        faiss.write_index(_user_index, settings.user_faiss_index_path)

# backward-compat alias
def save_faiss_index():
    save_user_faiss_index()


# ─────────────────────────────────────────────────────────────────
# Embedding
# ─────────────────────────────────────────────────────────────────

def create_embedding(text: str) -> List[float]:
    """Generate an L2-normalised embedding using Google Gemini."""
    text = text.strip()
    if not text:
        return [0.0] * DIMENSIONS
    try:
        response = genai.embed_content(
            model=settings.embedding_model,
            content=text,
            task_type="retrieval_document",
        )
        emb = np.array(response["embedding"], dtype=np.float32)
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm
        return emb.tolist()
    except Exception as e:
        logger.error("Error generating Gemini embedding: %s", e)
        return [0.0] * DIMENSIONS


# ─────────────────────────────────────────────────────────────────
# User document upload
# ─────────────────────────────────────────────────────────────────

def add_document_chunk(
    content: str,
    topic: str,
    source: str,
    chunk_index: int,
    db: Session,
) -> KnowledgeBase:
    """Store a user-uploaded chunk in PostgreSQL and add to USER FAISS index."""
    kb_entry = KnowledgeBase(
        content=content, topic=topic, source=source, chunk_index=chunk_index,
    )
    db.add(kb_entry)
    db.commit()
    db.refresh(kb_entry)

    embedding = create_embedding(content)
    idx = get_user_faiss_index()
    idx.add_with_ids(
        np.array([embedding], dtype=np.float32),
        np.array([kb_entry.id], dtype=np.int64),
    )
    save_user_faiss_index()
    return kb_entry


# ─────────────────────────────────────────────────────────────────
# Global KB search  (used by code analysis / game / roadmap RAG)
# ─────────────────────────────────────────────────────────────────

def search_knowledge_base(query: str, db: Session, k: int = 3) -> List[KnowledgeBase]:
    """
    Retrieve top-k chunks from the GLOBAL knowledge-base FAISS index.
    Falls back gracefully if the index is empty.
    """
    idx = get_kb_faiss_index()

    if idx.ntotal == 0:
        logger.warning("⚠️  Global FAISS index is empty — returning no RAG context.")
        return []

    query_emb = create_embedding(query)
    vector = np.array([query_emb], dtype=np.float32)

    # Request more candidates so threshold filtering still returns k results
    k_search = min(k * 3, idx.ntotal)
    distances, indices = idx.search(vector, k_search)

    kb_ids = [int(i) for i in indices[0] if i != -1]
    if not kb_ids:
        return []

    # Fetch from DB
    chunks = db.query(KnowledgeBase).filter(KnowledgeBase.id.in_(kb_ids)).all()
    chunk_map = {c.id: c for c in chunks}

    results = []
    for i, kb_id in enumerate(kb_ids):
        if kb_id not in chunk_map:
            continue
        dist = float(distances[0][i])
        if dist >= SIM_THRESHOLD:
            chunk = chunk_map[kb_id]
            chunk._sim_score = dist
            results.append(chunk)
        if len(results) >= k:
            break

    logger.info(
        "RAG search returned %d/%d chunks (threshold=%.2f, index has %d vectors).",
        len(results), k, SIM_THRESHOLD, idx.ntotal,
    )
    return results


# ─────────────────────────────────────────────────────────────────
# User document search  (Syllabus Q&A feature)
# ─────────────────────────────────────────────────────────────────

def search_user_documents(query: str, db: Session, k: int = 3) -> List[KnowledgeBase]:
    """Retrieve chunks from the USER document index (syllabus / notes)."""
    idx = get_user_faiss_index()
    if idx.ntotal == 0:
        return []

    query_emb = create_embedding(query)
    vector = np.array([query_emb], dtype=np.float32)
    k_search = min(k * 2, idx.ntotal)
    distances, indices = idx.search(vector, k_search)

    kb_ids = [int(i) for i in indices[0] if i != -1]
    if not kb_ids:
        return []

    chunks = db.query(KnowledgeBase).filter(KnowledgeBase.id.in_(kb_ids)).all()
    chunk_map = {c.id: c for c in chunks}
    results = []
    for i, kb_id in enumerate(kb_ids):
        if kb_id in chunk_map and float(distances[0][i]) >= SIM_THRESHOLD:
            c = chunk_map[kb_id]
            c._sim_score = float(distances[0][i])
            results.append(c)
        if len(results) >= k:
            break
    return results


# ─────────────────────────────────────────────────────────────────
# Startup sync  (called from main.py)
# ─────────────────────────────────────────────────────────────────

def sync_faiss_index(db: Session):
    """Ensure USER FAISS index is synced with PostgreSQL on startup."""
    idx = get_user_faiss_index()
    db_count = db.query(KnowledgeBase).count()
    if db_count > 0 and idx.ntotal != db_count:
        logger.warning(
            "USER FAISS index vectors (%d) != DB records (%d). Rebuilding…",
            idx.ntotal, db_count,
        )
        chunks = db.query(KnowledgeBase).all()
        vectors, ids = [], []
        for chunk in chunks:
            vectors.append(create_embedding(chunk.content))
            ids.append(chunk.id)
        if vectors:
            global _user_index
            _user_index = _make_flat_index()
            _user_index.add_with_ids(
                np.array(vectors, dtype=np.float32),
                np.array(ids, dtype=np.int64),
            )
            save_user_faiss_index()
            logger.info("✅ USER FAISS index rebuilt with %d chunks.", len(vectors))
