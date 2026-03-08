"""
services/roadmap_service.py
---------------------------
Generates a structured learning roadmap from the user's top error concepts
using Gemini LLM + RAG knowledge context. Stores the result in the DB.
"""
from __future__ import annotations
from typing import Optional
import json
import logging
from datetime import datetime

import google.generativeai as genai
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.roadmap import Roadmap
from app.services.pattern_service import get_top_concepts

logger = logging.getLogger(__name__)
settings = get_settings()
genai.configure(api_key=settings.gemini_api_key)

ROADMAP_SYSTEM_PROMPT = """You are an expert learning path designer for programming students.
Create a structured roadmap based on the student's weak areas AND the available learning resources.
Return ONLY valid JSON in exactly this format:
{
  "title": "Your Personalized Learning Roadmap",
  "total_weeks": <int>,
  "weeks": [
    {
      "week": <int>,
      "focus": "<main theme>",
      "topics": [
        {
          "name": "<topic name>",
          "why": "<why this helps the student>",
          "estimated_time": "<e.g. 4 hours>",
          "resources": ["<resource hint>"]
        }
      ],
      "practice_goal": "<what to submit this week>"
    }
  ]
}"""


def _get_rag_context(db: Session, concepts: list[str]) -> str:
    """
    Retrieve knowledge base chunks relevant to the user's weak concepts.
    Injects these as learning resources into the roadmap prompt.
    """
    try:
        from app.models.knowledge_base import KnowledgeBase
        chunks = []
        for concept in concepts:
            rows = (
                db.query(KnowledgeBase)
                .filter(KnowledgeBase.topic.ilike(f"%{concept}%"))
                .limit(2)
                .all()
            )
            chunks.extend(rows)
        if not chunks:
            chunks = db.query(KnowledgeBase).limit(6).all()
        return "\n\n".join(f"[{c.topic}] {c.content[:300]}" for c in chunks)
    except Exception as exc:
        logger.warning("RAG context fetch failed for roadmap: %s", exc)
        return ""


async def generate_roadmap(
    db: Session,
    user_id: str,
    skill_level: str = "beginner",
    goal: str = "placement",
) -> dict:
    """Generate and persist a personalized roadmap for the user."""
    top_concepts = get_top_concepts(db, user_id, limit=3)

    if not top_concepts:
        return _default_roadmap(skill_level, goal)

    concept_names = [c["concept"] for c in top_concepts]

    # Fetch RAG knowledge context for those concepts
    rag_context = _get_rag_context(db, concept_names)
    context_section = (
        f"\n\nAvailable learning resources from knowledge base:\n{rag_context}"
        if rag_context
        else ""
    )

    user_msg = (
        f"Student profile:\n- Skill level: {skill_level}\n- Goal: {goal}\n"
        f"- Weakest concepts: {', '.join(concept_names)}\n\n"
        f"User struggles with: {', '.join(concept_names)}\n"
        f"{context_section}\n\n"
        "Generate a 6-week coding roadmap addressing these weaknesses toward placement readiness.\n"
        "Use the available resources above where relevant to suggest study materials per topic.\n"
        "Return ONLY the JSON object."
    )

    try:
        model = genai.GenerativeModel(
            model_name=settings.model_name,
            system_instruction=ROADMAP_SYSTEM_PROMPT
        )
        response = await model.generate_content_async(
            user_msg,
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                response_mime_type="application/json"
            )
        )
        roadmap_data = json.loads(response.text or "{}")
    except Exception as e:
        logger.error("Roadmap LLM generation failed: %s — using default", e)
        roadmap_data = _default_roadmap(skill_level, goal)

    # Version bump if one already exists
    existing = (
        db.query(Roadmap)
        .filter(Roadmap.user_id == user_id)
        .order_by(Roadmap.version.desc())
        .first()
    )
    version = (existing.version + 1) if existing else 1
    db.add(Roadmap(
        user_id=user_id,
        roadmap_data=roadmap_data,
        version=version,
        generated_at=datetime.utcnow()
    ))
    db.flush()
    return roadmap_data


def get_latest_roadmap(db: Session, user_id: str) -> Optional[dict]:
    """Fetch the most recent roadmap for a user from DB."""
    roadmap = (
        db.query(Roadmap)
        .filter(Roadmap.user_id == user_id)
        .order_by(Roadmap.version.desc())
        .first()
    )
    return roadmap.roadmap_data if roadmap else None


def _default_roadmap(skill_level: str, goal: str) -> dict:
    """Static fallback roadmap for new users or LLM failures."""
    return {
        "title": "Your Personalized Learning Roadmap",
        "total_weeks": 6,
        "weeks": [
            {"week": 1, "focus": "Python Fundamentals", "topics": [
                {"name": "Variables & Data Types", "why": "Foundation of all programs", "estimated_time": "3 hours", "resources": ["Python docs", "W3Schools Python"]},
                {"name": "Control Flow", "why": "Loops and conditions are tested in every interview", "estimated_time": "4 hours", "resources": ["LeetCode easy"]},
            ], "practice_goal": "Submit 3 loop-based solutions"},
            {"week": 2, "focus": "Functions & Recursion", "topics": [
                {"name": "Functions & Scope", "why": "Clean code starts with good functions", "estimated_time": "3 hours", "resources": ["Exercism Python"]},
                {"name": "Recursion Fundamentals", "why": "Recursion questions are common in placements", "estimated_time": "5 hours", "resources": ["Visualize recursion tree on pythontutor.com"]},
            ], "practice_goal": "Solve 5 recursion problems"},
            {"week": 3, "focus": "Data Structures", "topics": [
                {"name": "Arrays & Lists", "why": "Most fundamental DS", "estimated_time": "4 hours", "resources": ["LeetCode array tag"]},
                {"name": "Stacks & Queues", "why": "Used in BFS/DFS and system design", "estimated_time": "4 hours", "resources": ["GeeksforGeeks"]},
            ], "practice_goal": "Submit 5 DS problems"},
            {"week": 4, "focus": "Algorithms", "topics": [
                {"name": "Sorting Algorithms", "why": "Core CS knowledge tested in interviews", "estimated_time": "4 hours", "resources": ["VisuAlgo"]},
                {"name": "Binary Search", "why": "Pattern used in many medium problems", "estimated_time": "3 hours", "resources": ["LeetCode binary search"]},
            ], "practice_goal": "Solve 8 algorithm problems"},
            {"week": 5, "focus": "Dynamic Programming", "topics": [
                {"name": "Memoization", "why": "Converts exponential to polynomial time", "estimated_time": "5 hours", "resources": ["NeetCode DP playlist"]},
            ], "practice_goal": "Solve 5 DP problems"},
            {"week": 6, "focus": "Mock Interviews", "topics": [
                {"name": "Timed Problem Solving", "why": "Simulate real interview pressure", "estimated_time": "6 hours", "resources": ["Pramp", "Interviewing.io"]},
            ], "practice_goal": "Complete 3 mock interviews"},
        ],
    }
