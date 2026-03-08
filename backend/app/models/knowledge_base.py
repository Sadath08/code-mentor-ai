"""models/knowledge_base.py"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from app.database import Base

class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    topic = Column(String(255), nullable=True)
    source = Column(String(255), nullable=True)
    chunk_index = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
