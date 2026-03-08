"""
services/game_service.py
------------------------
Generates coding game questions targeted at the user's weakest concept.
Features:
  - Batch generation: 5 questions per session via LLM
  - RAG context injection from KB for each concept
  - DB-level question caching (6h TTL)
  - Static fallback set when LLM is unavailable
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import google.generativeai as genai
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.game_question import GameQuestion
from app.services.pattern_service import get_top_concepts

logger = logging.getLogger(__name__)
settings = get_settings()
genai.configure(api_key=settings.gemini_api_key)

GAME_TYPES = ["debug_the_bug", "predict_output", "code_jumble", "syntax_sprint", "trivia"]
CACHE_TTL_HOURS = 6  # Re-use cached questions for up to 6 hours


# ─────────────────────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────────────────────

BATCH_GAME_PROMPT = """You are a coding game designer for programming students preparing for placements.
Generate exactly 5 coding practice questions based on the provided knowledge context.
Return ONLY valid JSON — no markdown, no extra text.

Required format:
{
  "questions": [
    {
      "question": "<the question prompt>",
      "code_snippet": "<code if relevant, else empty string>",
      "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
      "correct_answer": "<just the letter A, B, C or D>",
      "explanation": "<why this is the correct answer>",
      "hint": "<optional hint>",
      "difficulty": "<easy|medium|hard>",
      "points": <100|150|200>
    }
  ]
}

Rules:
1. All 5 questions must target the given concept.
2. Vary difficulty: at least 2 easy, 2 medium, 1 hard.
3. Use real Python code snippets where relevant.
4. explanations must be educational and clear.
5. correct_answer must be exactly one of: A, B, C, D
"""


# ─────────────────────────────────────────────────────────────────────────────
# Static Fallback (5 questions)
# ─────────────────────────────────────────────────────────────────────────────

FALLBACK_QUESTIONS = {
    "questions": [
        {
            "question": "What is the output of range(5)?",
            "code_snippet": "for i in range(5):\n    print(i)",
            "options": ["A) 1 2 3 4 5", "B) 0 1 2 3 4", "C) 0 1 2 3 4 5", "D) Error"],
            "correct_answer": "B",
            "explanation": "range(5) generates numbers 0 to 4 (exclusive of 5).",
            "hint": "range() is 0-indexed by default.",
            "difficulty": "easy", "points": 100,
        },
        {
            "question": "Find the bug in this loop:",
            "code_snippet": "nums = [1, 2, 3]\nfor i in range(len(nums) + 1):\n    print(nums[i])",
            "options": ["A) range(len(nums)+1) should be range(len(nums))", "B) print → return", "C) nums definition is wrong", "D) No bug"],
            "correct_answer": "A",
            "explanation": "range(len(nums)+1) causes IndexError on the last iteration. Use range(len(nums)).",
            "hint": "Check loop boundary vs list length.", "difficulty": "easy", "points": 100,
        },
        {
            "question": "What does fib(4) return?",
            "code_snippet": "def fib(n):\n    if n <= 1: return n\n    return fib(n-1) + fib(n-2)",
            "options": ["A) 2", "B) 3", "C) 4", "D) 5"],
            "correct_answer": "B",
            "explanation": "fib(4) = fib(3) + fib(2) = 2 + 1 = 3. Trace recursively.",
            "hint": "Trace the recursion tree step by step.", "difficulty": "medium", "points": 150,
        },
        {
            "question": "What is the time complexity of accessing an element in a Python dict?",
            "code_snippet": "d = {'a': 1, 'b': 2}\nprint(d['a'])",
            "options": ["A) O(n)", "B) O(log n)", "C) O(1)", "D) O(n²)"],
            "correct_answer": "C",
            "explanation": "Dictionary lookup is O(1) average due to hash tables.",
            "hint": "Think about how hash maps work.", "difficulty": "medium", "points": 150,
        },
        {
            "question": "Which sorting algorithm has O(n log n) worst-case complexity?",
            "code_snippet": "",
            "options": ["A) Bubble Sort", "B) Selection Sort", "C) Merge Sort", "D) Insertion Sort"],
            "correct_answer": "C",
            "explanation": "Merge sort always runs in O(n log n) due to its divide-and-conquer approach, unlike quicksort which degrades to O(n²) in worst case.",
            "hint": "Think about divide-and-conquer.", "difficulty": "hard", "points": 200,
        },
    ]
}


# ─────────────────────────────────────────────────────────────────────────────
# RAG Context Helper
# ─────────────────────────────────────────────────────────────────────────────

def _get_rag_context(db: Session, concept: str) -> tuple[str, int]:
    """
    Retrieve knowledge base chunks for the concept.
    Returns (context_text, num_chunks_used).
    """
    try:
        from app.models.knowledge_base import KnowledgeBase
        chunks = (
            db.query(KnowledgeBase)
            .filter(KnowledgeBase.topic.ilike(f"%{concept}%"))
            .limit(3)
            .all()
        )
        if not chunks:
            chunks = db.query(KnowledgeBase).limit(3).all()
        context = "\n\n".join(c.content for c in chunks)
        return context, len(chunks)
    except Exception as exc:
        logger.warning("RAG context fetch failed: %s", exc)
        return "", 0


# ─────────────────────────────────────────────────────────────────────────────
# Cache Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_cached_questions(db: Session, concept: str) -> Optional[dict]:
    """Retrieve fresh cached questions from DB (< 6h old)."""
    try:
        cutoff = datetime.utcnow() - timedelta(hours=CACHE_TTL_HOURS)
        row = (
            db.query(GameQuestion)
            .filter(
                GameQuestion.concept == concept,
                GameQuestion.created_at > cutoff,
            )
            .order_by(GameQuestion.created_at.desc())
            .first()
        )
        if row:
            logger.info("Cache HIT for concept=%s", concept)
            return row.question_data
    except Exception as exc:
        logger.warning("Cache read failed: %s", exc)
    return None


def _save_questions_to_cache(db: Session, concept: str, data: dict, game_type: str):
    """Persist generated questions to DB cache."""
    try:
        db.add(GameQuestion(
            game_type=game_type,
            concept=concept,
            question_data=data,
        ))
        db.flush()
    except Exception as exc:
        logger.warning("Cache write failed: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

async def get_game_questions(
    db: Session,
    game_type: str,
    user_id: Optional[str] = None,
) -> dict:
    """
    Generate or retrieve 5 game questions for a session.

    Flow:
      1. Get user's weakest concept from error_patterns
      2. Check DB cache (6h TTL)
      3. Retrieve RAG context from knowledge base
      4. Generate 5 questions via Gemini LLM
      5. Cache results in DB
      6. Return questions + metadata
    """
    # Step 1: Identify weakest concept
    target_concept = "general_programming"
    if user_id:
        top = get_top_concepts(db, user_id, limit=1)
        if top:
            target_concept = top[0]["concept"]

    # Step 2: Cache check
    cached = _get_cached_questions(db, target_concept)
    if cached:
        return {
            "concept": target_concept,
            "game_type": game_type,
            "rag_chunks_used": cached.get("rag_chunks_used", 0),
            "cached": True,
            "questions": cached.get("questions", []),
        }

    # Step 3: RAG context
    rag_context, chunks_used = _get_rag_context(db, target_concept)
    context_section = (
        f"Using this programming knowledge:\n{rag_context}\n\n"
        if rag_context
        else ""
    )

    # Step 4: Generate 5 questions via Gemini
    try:
        model = genai.GenerativeModel(
            model_name=settings.model_name,
            system_instruction=BATCH_GAME_PROMPT,
        )
        user_msg = (
            f"{context_section}"
            f"Generate 5 coding interview practice questions about the concept: '{target_concept}'.\n"
            f"Game type style: {game_type}. Use Python code examples.\n"
            "Return ONLY the JSON object."
        )
        response = await model.generate_content_async(
            user_msg,
            generation_config=genai.types.GenerationConfig(
                temperature=0.55,
                max_output_tokens=3000,
                response_mime_type="application/json",
            ),
        )
        raw = response.text or "{}"
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        result = json.loads(raw)
        questions = result.get("questions", [])

        # Ensure at least 1 question
        if not questions:
            raise ValueError("LLM returned empty questions list")

        payload = {
            "questions": questions,
            "rag_chunks_used": chunks_used,
        }

        # Step 5: Cache in DB
        _save_questions_to_cache(db, target_concept, payload, game_type)
        db.commit()

        return {
            "concept": target_concept,
            "game_type": game_type,
            "rag_chunks_used": chunks_used,
            "cached": False,
            "questions": questions,
        }

    except Exception as exc:
        logger.error("Batch game question generation failed: %s", exc)
        fb = FALLBACK_QUESTIONS.copy()
        return {
            "concept": target_concept,
            "game_type": game_type,
            "rag_chunks_used": 0,
            "cached": False,
            "questions": fb["questions"],
        }


# Keep single-question generator for backward compatibility
async def generate_question(
    db: Session,
    game_type: str,
    user_id: Optional[str] = None,
) -> dict:
    """Returns a single question (legacy endpoint support)."""
    result = await get_game_questions(db, game_type, user_id)
    questions = result.get("questions", [])
    single = questions[0] if questions else FALLBACK_QUESTIONS["questions"][0]
    single.setdefault("game_type", game_type)
    single.setdefault("concept", result.get("concept", "general"))
    single.setdefault("points", 100)
    return single
