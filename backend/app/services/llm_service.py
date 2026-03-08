"""
services/llm_service.py
-----------------------
Multi-provider LLM analysis with automatic fallback.

Priority order:
  1. OpenAI   (gpt-4o-mini)       – if OPENAI_API_KEY starts with "sk-"
  2. Groq     (llama-3.3-70b)     – if GROQ_API_KEY starts with "gsk_"
  3. Gemini   (gemini-2.0-flash)  – always available as last resort

Each provider returns the same structured JSON consumed by the frontend.
All calls run in asyncio.to_thread so FastAPI stays non-blocking.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any

from dotenv import load_dotenv

load_dotenv(override=True)
logger = logging.getLogger(__name__)

# ── Env / constants ──────────────────────────────────────────────────────────
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL    = os.getenv("OPENAI_MODEL",   "gpt-4o-mini")

GROQ_API_KEY    = os.getenv("GROQ_API_KEY",   "")
GROQ_MODEL      = os.getenv("GROQ_MODEL",     "llama-3.3-70b-versatile")

GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL    = os.getenv("GEMINI_MODEL",   "models/gemini-2.0-flash")

MAX_CODE_CHARS  = 2000

# ── Availability flags ───────────────────────────────────────────────────────
def _has_openai()  -> bool: return bool(OPENAI_API_KEY) and OPENAI_API_KEY.startswith("sk-")
def _has_groq()    -> bool: return bool(GROQ_API_KEY)   and GROQ_API_KEY.startswith("gsk_")
def _has_gemini()  -> bool: return bool(GEMINI_API_KEY)

# ── System prompt (shared by all providers) ──────────────────────────────────
SYSTEM_PROMPT = """\
You are an expert programming mentor.
Analyse the submitted code and return STRICT JSON — no markdown, no extra text.

OUTPUT FORMAT:
{
  "confidence_score": 85.5,
  "issues": [
    {
      "type": "syntax | logic | performance",
      "concept": "loops",
      "what": "one-sentence description",
      "why": "clear explanation of WHY this is a bug",
      "hints": ["nudge 1", "nudge 2"],
      "fix": "concrete fix instruction",
      "fixed_code": "corrected snippet"
    }
  ],
  "best_practices": ["what they did well"],
  "overall_feedback": "2-3 sentence summary",
  "time_complexity": "O(n)",
  "space_complexity": "O(1)",
  "concepts_to_study": ["concept1", "concept2"],
  "is_recurring": false,
  "encouraging_message": "Keep going!"
}

Return ONLY the JSON. No markdown, no prefixes.
"""


# ── Provider call functions ──────────────────────────────────────────────────

async def _call_openai(user_prompt: str) -> str:
    """Call OpenAI (gpt-4o-mini) and return raw JSON string."""
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = await asyncio.to_thread(
        client.chat.completions.create,
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=1500,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content or "{}"


async def _call_groq(user_prompt: str) -> str:
    """Call Groq (Llama-3.3-70b) and return raw JSON string."""
    from groq import AsyncGroq
    client = AsyncGroq(api_key=GROQ_API_KEY)
    response = await client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=1500,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content or "{}"


async def _call_gemini(user_prompt: str) -> str:
    """Call Gemini (2.0-flash) and return raw text (may include markdown fences)."""
    import google.generativeai as genai
    import warnings; warnings.filterwarnings("ignore")
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)
    response = await asyncio.to_thread(
        model.generate_content,
        f"{SYSTEM_PROMPT}\n\n{user_prompt}",
        generation_config={"temperature": 0.2, "max_output_tokens": 1500},
    )
    return response.text or ""


# ── JSON extraction helper ───────────────────────────────────────────────────

def _extract_json(raw: str) -> dict:
    """Strip markdown fences and extract the first JSON object."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON block found in: {raw[:120]}")
    return json.loads(match.group(0))


# ── Normalise output to a stable frontend schema ─────────────────────────────

def _normalise(data: dict, is_recurring: bool) -> dict:
    score = float(data.get("confidence_score", 0.5))
    if score > 1.0:
        score = score / 100.0          # 85.5 → 0.855
    data["confidence_score"] = score

    errors = data.get("issues", data.get("errors", []))
    data["errors"] = errors if isinstance(errors, list) else []

    data.setdefault("overall_feedback",  data.get("feedback_summary", "Analysis complete."))
    data.setdefault("concepts_to_study", data.get("study_topics", ["programming"]))
    data.setdefault("is_recurring",      is_recurring)
    data.setdefault("best_practices",    [])
    data.setdefault("encouraging_message", "Keep coding! 🚀")
    return data


# ── Main entry-point ─────────────────────────────────────────────────────────

async def analyze_code(
    code: str,
    language: str,
    context: str,
    code_features: dict[str, Any],
    is_recurring: bool = False,
) -> dict:
    """
    Analyse code with the best available LLM (OpenAI → Groq → Gemini).
    Returns structured JSON compatible with the frontend schema.
    """
    if len(code) > MAX_CODE_CHARS:
        code = code[:MAX_CODE_CHARS]

    suspected    = ", ".join(code_features.get("suspected_concepts", []))
    ctx_section  = context if context else "No specific KB context."
    recur_note   = "⚠️ Student makes this mistake often." if is_recurring else ""

    user_prompt = f"""Language: {language}
Suspected concepts: {suspected}
{recur_note}

=== KNOWLEDGE BASE ===
{ctx_section}

=== CODE ===
```{language}
{code}
```
"""

    # ── Select backend ───────────────────────────────────────────────────────
    if _has_openai():
        backend = "openai"
    elif _has_groq():
        backend = "groq"
    elif _has_gemini():
        backend = "gemini"
    else:
        logger.error("No LLM API key configured!")
        return _fallback_feedback("No LLM API key configured. Set OPENAI_API_KEY, GROQ_API_KEY, or GEMINI_API_KEY.")

    logger.info("🤖 LLM backend selected: %s", backend)

    # ── Call provider with one automatic retry on failure ────────────────────
    provider_order = [backend]
    # Append the remaining providers as fallbacks (in priority order)
    for p in ["openai", "groq", "gemini"]:
        if p != backend and (
            (p == "openai"  and _has_openai()) or
            (p == "groq"    and _has_groq())   or
            (p == "gemini"  and _has_gemini())
        ):
            provider_order.append(p)

    last_error = ""
    for attempt_backend in provider_order:
        try:
            logger.info("Attempting provider: %s", attempt_backend)
            if attempt_backend == "openai":
                raw = await _call_openai(user_prompt)
            elif attempt_backend == "groq":
                raw = await _call_groq(user_prompt)
            else:
                raw = await _call_gemini(user_prompt)

            data = _extract_json(raw)
            data = _normalise(data, is_recurring)

            logger.info("✅ %s analysis success — score=%.2f, %d issue(s)",
                        attempt_backend, data["confidence_score"], len(data["errors"]))
            return data

        except Exception as e:
            last_error = f"{attempt_backend}: {type(e).__name__} – {e}"
            logger.warning("Provider %s failed: %s", attempt_backend, e)
            continue   # try next provider

    # All providers exhausted
    logger.error("\n" + "=" * 50)
    logger.error("🚨 ALL LLM PROVIDERS FAILED 🚨")
    logger.error("Last error: %s", last_error)
    logger.error("=" * 50)
    return _fallback_feedback(last_error)


# ── Fallback ─────────────────────────────────────────────────────────────────

def _fallback_feedback(err_msg: str = "") -> dict:
    """Returned when every LLM provider fails."""
    return {
        "errors": [{
            "type": "system_error",
            "concept": "general",
            "what": "AI Pipeline Error",
            "why": f"Error: {err_msg}" if err_msg else "All LLM providers failed.",
            "fix": "Check OPENAI_API_KEY / GROQ_API_KEY / GEMINI_API_KEY in .env",
            "hints": [],
            "fixed_code": "",
        }],
        "best_practices": [],
        "overall_feedback": "AI analysis incomplete — please retry.",
        "time_complexity":  "Unknown",
        "space_complexity":  "Unknown",
        "concepts_to_study": ["general_programming"],
        "confidence_score":  0.3,
        "is_recurring":      False,
        "encouraging_message": "Keep coding! The system will be back shortly.",
    }
