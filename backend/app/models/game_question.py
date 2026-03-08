"""
models/game_question.py
-----------------------
Cache for LLM-generated game questions.
Questions are stored keyed by (game_type, concept) to avoid
re-calling the LLM for similar requests (performance optimization).
"""
from __future__ import annotations
from datetime import datetime

from sqlalchemy import Column, String, JSON, DateTime, Integer

from app.database import Base


class GameQuestion(Base):
    __tablename__ = "game_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_type = Column(String(64), nullable=False, index=True)
    concept = Column(String(128), nullable=False, index=True)
    question_data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<GameQuestion id={self.id} game_type={self.game_type} concept={self.concept}>"
