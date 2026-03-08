"""
routes/ask.py
-------------
POST /api/ask  — answer a question using the user's personal syllabus/notes RAG index.
Each user's notes are stored in knowledge_base/user_indexes/{user_id}/ (separate from global KB).
"""
from __future__ import annotations

import asyncio
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import get_settings

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)


async def _generate_answer(prompt: str) -> str:
    """Generate an answer using the best available LLM (Gemini free-tier primary)."""
    try:
        import google.generativeai as genai
        import warnings; warnings.filterwarnings("ignore")
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(settings.gemini_model)
        response = await asyncio.to_thread(
            model.generate_content, prompt,
            generation_config={"temperature": 0.3, "max_output_tokens": 800}
        )
        return response.text.strip()
    except Exception as e:
        logger.error("LLM answer generation failed: %s", e)
        return f"Sorry, I had trouble generating an answer. Please try again. (Error: {e})"


@router.post("/ask")
async def ask_syllabus(payload: dict, db: Session = Depends(get_db)):
    """
    Answer a question using only the user's personal uploaded notes (not the global KB).
    Falls back to global KB if user has no personal notes yet.
    """
    question = payload.get("question", "").strip()
    user_id  = payload.get("user_id", "").strip()

    if not question:
        return {"answer": "Please enter a question.", "sources": [], "has_context": False}

    # ── Step 1: retrieve from user's personal index ──────────────────────────
    from app.services.syllabus_service import retrieve_user_context
    results = retrieve_user_context(question, user_id, k=4) if user_id else []

    # ── Step 2: if no personal notes, tell user to upload ───────────────────
    if not results:
        return {
            "answer": "📂 No notes found.\n\nUpload your syllabus PDFs using the '+ Upload Notes' button above, then ask any question from your material!",
            "sources": [],
            "has_context": False,
            "chunks_used": 0,
        }

    # ── Step 3: build context from retrieved chunks ───────────────────────────
    context = "\n\n".join(
        f"[Source: {r.get('source', 'Unknown')} | Topic: {r.get('topic', 'syllabus')}]\n{r.get('content', '')}"
        for r in results
    )

    # ── Step 4: generate answer ───────────────────────────────────────────────
    prompt = f"""You are a helpful AI tutor for engineering students.
Answer the student's question using ONLY the provided notes context.

NOTES CONTEXT:
{context}

Student Question: {question}

Rules:
- Answer ONLY from the context above
- If the answer is not in the notes, say: "This topic isn't covered in your uploaded notes."
- Be clear, structured, and beginner-friendly
- Add code examples where useful
- End with: "📌 Source: [document name from context]"
"""
    answer = await _generate_answer(prompt)

    # ── Step 5: return response ───────────────────────────────────────────────
    return {
        "answer": answer,
        "sources": [
            {
                "source": r.get("source", "Unknown"),
                "topic": r.get("topic", "syllabus"),
                "preview": r.get("content", "")[:150] + "...",
                "similarity": r.get("similarity", 0.0),
            }
            for r in results
        ],
        "has_context": True,
        "chunks_used": len(results),
    }


# ── CS Concept Explanation ────────────────────────────────────────────────────

CONCEPT_PROMPT = """\
You are an expert Computer Science tutor.
You MUST return ONLY a single valid JSON object — no markdown, no prose, no code fences.

The user is asking about: "{question}" (language preference: {language})

Return this EXACT JSON structure:
{{
  "definition": "one-paragraph definition",
  "layman": "explain like the student is 10 years old",
  "how_it_works": ["step 1", "step 2", "step 3"],
  "code_example": {{
    "code": "working {language} code snippet",
    "explanation": "line-by-line short explanation"
  }},
  "complexity": {{
    "time": "O(...) with brief reason",
    "space": "O(...) with brief reason"
  }},
  "real_world_uses": ["use 1", "use 2", "use 3"],
  "common_mistakes": ["mistake 1", "mistake 2", "mistake 3"],
  "interview_questions": ["Q1?", "Q2?", "Q3?"],
  "quick_revision": ["bullet 1", "bullet 2", "bullet 3", "bullet 4", "bullet 5"],
  "related_topics": ["Topic A", "Topic B", "Topic C"]
}}

Return ONLY the JSON. No extra text.
"""


@router.post("/ask/concept")
async def explain_concept(payload: dict):
    """
    Return a structured 10-section explanation of any CS concept using the best
    available LLM (OpenAI → Groq → Gemini).
    """
    import re, json as _json
    from app.services.llm_service import _has_openai, _has_groq, _has_gemini
    from app.services.llm_service import OPENAI_API_KEY, OPENAI_MODEL, GROQ_API_KEY, GROQ_MODEL, GEMINI_API_KEY, GEMINI_MODEL

    question = payload.get("question", "").strip()
    language = payload.get("language", "python")

    if not question:
        return {"error": "question is required"}

    prompt = CONCEPT_PROMPT.format(question=question, language=language)

    # Select provider
    if _has_openai():
        provider = "openai"
    elif _has_groq():
        provider = "groq"
    elif _has_gemini():
        provider = "gemini"
    else:
        return {"error": "No LLM API key configured"}

    logger.info("Concept explanation via %s: %s", provider, question)

    try:
        if provider == "openai":
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            def _call():
                r = client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3, max_tokens=1800,
                    response_format={"type": "json_object"},
                )
                return r.choices[0].message.content or "{}"
            raw = await asyncio.to_thread(_call)

        elif provider == "groq":
            from groq import AsyncGroq
            client = AsyncGroq(api_key=GROQ_API_KEY)
            resp = await client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3, max_tokens=1800,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content or "{}"

        else:  # gemini
            import google.generativeai as genai
            import warnings; warnings.filterwarnings("ignore")
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel(GEMINI_MODEL)
            resp = await asyncio.to_thread(
                model.generate_content, prompt,
                generation_config={"temperature": 0.3, "max_output_tokens": 1800},
            )
            raw = resp.text or ""

        # Strip markdown fences if present
        raw = raw.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError("No JSON block in response")
        data = _json.loads(match.group(0))
        return data

    except Exception as e:
        logger.error("Concept explanation failed: %s", e)
        return {
            "definition": f"Sorry, the AI had trouble explaining '{question}'. Please try again.",
            "layman": str(e),
            "how_it_works": [],
            "code_example": {"code": "", "explanation": ""},
            "complexity": {"time": "N/A", "space": "N/A"},
            "real_world_uses": [],
            "common_mistakes": [],
            "interview_questions": [],
            "quick_revision": [],
            "related_topics": [],
        }

