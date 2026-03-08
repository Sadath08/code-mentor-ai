"""models/knowledge_document.py – Tracks documents ingested into the FAISS RAG index."""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class KnowledgeDocument(Base):
    """
    Persists metadata for every document uploaded to the RAG knowledge base.
    Actual content lives in the FAISS index + metadata.json on disk.
    """
    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(10), default="text")   # pdf | docx | text
    original_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)          # FAISS vectors added
    status: Mapped[str] = mapped_column(String(20), default="processing") # processing|indexed|error
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(30), default="general")  # programming language tag
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    indexed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
