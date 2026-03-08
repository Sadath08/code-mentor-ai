"""
routes/documents.py
--------------------
REST endpoints for RAG knowledge-base document management.

POST /api/documents/upload  – ingest a PDF, DOCX, or TXT file
GET  /api/documents/        – list all indexed documents
DELETE /api/documents/{doc_id} – soft-delete a document record
POST /api/documents/query   – direct RAG query (debug / preview)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models.knowledge_document import KnowledgeDocument
from app.services.document_service import ingest_document

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])

# ──────────────────────────────────────────────────────────────
# Pydantic response schemas
# ──────────────────────────────────────────────────────────────

class DocumentOut(BaseModel):
    id: str
    filename: str
    file_type: str
    chunk_count: int
    status: str
    language: str
    uploaded_at: str
    indexed_at: Optional[str]

    class Config:
        from_attributes = True


class QueryRequest(BaseModel):
    query: str
    language: str = "general"
    top_k: int = 4


class QueryResponse(BaseModel):
    query: str
    context: str
    language: str


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "docx",
    "text/plain": "text",
    "text/markdown": "text",
    "text/x-python": "text",
    "application/octet-stream": "text",  # fallback for generic uploads
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def _doc_to_out(doc: KnowledgeDocument) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        filename=doc.filename,
        file_type=doc.file_type,
        chunk_count=doc.chunk_count,
        status=doc.status,
        language=doc.language,
        uploaded_at=doc.uploaded_at.isoformat(),
        indexed_at=doc.indexed_at.isoformat() if doc.indexed_at else None,
    )


# ──────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────

@router.get("/rag-status")
def rag_status():
    """Return the health and stats of the RAG engine."""
    from rag import get_faiss_index
    idx = get_faiss_index()
    return {"mode": "faiss", "index_type": "IndexIDMap(IndexFlatL2)", "vectors": idx.ntotal, "score_threshold": "L2 distance"}


@router.post("/upload", response_model=DocumentOut, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    language: str = Form(default="general"),
    db: Session = Depends(get_db),
):
    """
    Upload a PDF, DOCX, or plain-text file and ingest it into the RAG index.
    - language: optional tag (e.g. 'python', 'javascript') for retrieval filtering.
    """
    # Content-type check (also accept by extension as fallback)
    content_type = file.content_type or "application/octet-stream"
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    file_type = ALLOWED_TYPES.get(content_type) or (
        "pdf" if ext == "pdf" else
        "docx" if ext in ("docx", "doc") else
        "text"
    )

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is {MAX_FILE_SIZE // (1024*1024)} MB.",
        )
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Persist initial record
    doc = KnowledgeDocument(
        filename=file.filename or "unknown",
        file_type=file_type,
        original_size_bytes=len(data),
        language=language,
        status="processing",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Run ingestion (synchronous-ish; runs in the request cycle for simplicity)
    chunk_count, status = await ingest_document(
        data=data,
        filename=file.filename or "unknown",
        file_type=file_type,
        language=language,
    )

    doc.chunk_count = chunk_count
    doc.status = "indexed" if status == "indexed" else "error"
    doc.error_message = None if status == "indexed" else status
    doc.indexed_at = datetime.now(timezone.utc) if status == "indexed" else None
    db.commit()
    db.refresh(doc)

    logger.info(
        "Document '%s' ingested: %d chunks, status=%s",
        doc.filename, chunk_count, doc.status,
    )
    return _doc_to_out(doc)


@router.get("/", response_model=List[DocumentOut])
def list_documents(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Return all knowledge-base documents sorted by upload date."""
    docs = (
        db.query(KnowledgeDocument)
        .order_by(KnowledgeDocument.uploaded_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [_doc_to_out(d) for d in docs]


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: str, db: Session = Depends(get_db)):
    """Fetch a single document record by ID."""
    doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return _doc_to_out(doc)


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: str, db: Session = Depends(get_db)):
    """
    Remove a document record from the database.
    Note: does NOT remove the vectors from the FAISS index
    (rebuild the index via build_kb.py to fully remove content).
    """
    doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    db.delete(doc)
    db.commit()
    return None


@router.post("/query", response_model=QueryResponse)
async def query_rag(payload: QueryRequest, db: Session = Depends(get_db)):
    """
    Debug endpoint – run a direct RAG retrieval query and see the context
    that would be injected into the LLM prompt.
    """
    from rag import search_knowledge_base
    kb_chunks = search_knowledge_base(payload.query, db, k=payload.top_k)
    context = "\n\n---\n\n".join([chunk.content for chunk in kb_chunks]) if kb_chunks else "No relevant knowledge found."
    
    return QueryResponse(
        query=payload.query,
        context=context,
        language=payload.language,
    )


# ──────────────────────────────────────────────────────────────
# 📚 User-specific Syllabus Upload (personal RAG)
# ──────────────────────────────────────────────────────────────

@router.post("/upload-syllabus", status_code=201)
async def upload_syllabus(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Upload a personal note/syllabus PDF, DOCX, or text file.
    Builds a user-specific FAISS index — completely separate from the global KB.
    """
    from app.services.syllabus_service import ingest_user_document

    content_type = file.content_type or "application/octet-stream"
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    file_type = ALLOWED_TYPES.get(content_type) or (
        "pdf" if ext == "pdf" else
        "docx" if ext in ("docx", "doc") else
        "text"
    )

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB).")
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    chunk_count, status = await __import__("asyncio").to_thread(
        ingest_user_document,
        data, file.filename or "unknown", file_type, user_id
    )

    if "failed" in status or status == "no_content":
        raise HTTPException(status_code=422, detail=f"Ingestion failed: {status}")

    logger.info("Syllabus upload: user=%s file=%s chunks=%d", user_id, file.filename, chunk_count)
    return {
        "status": "success",
        "filename": file.filename,
        "chunks_indexed": chunk_count,
    }


@router.get("/user-notes/{user_id}")
def list_user_notes(user_id: str):
    """Return the list of filenames the user has uploaded as personal notes."""
    from app.services.syllabus_service import list_user_documents
    files = list_user_documents(user_id)
    return {"user_id": user_id, "files": files}

