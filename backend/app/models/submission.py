"""
models/submission.py – Code submission model for CodeMentor AI
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Text, JSON, ForeignKey, Float
from sqlalchemy.orm import relationship

from app.database import Base


class Submission(Base):
    __tablename__ = "submissions"

    # Unique submission ID (job_id)
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # User who submitted the code
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)

    # Programming language
    language = Column(String(30), default="python")

    # Submitted source code
    code = Column(Text, nullable=False)

    # Optional problem context provided by user
    problem_description = Column(Text, default="")

    # Job lifecycle: processing → completed | failed
    status = Column(String(20), default="processing", index=True)

    # Full AI feedback JSON blob
    feedback = Column(JSON, nullable=True)

    # Normalised AI confidence (0.0 – 1.0)
    confidence_score = Column(Float, default=0.0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationship
    user = relationship("User", back_populates="submissions")
