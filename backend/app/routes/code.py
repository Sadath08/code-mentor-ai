"""
routes/code.py
--------------
POST /api/code/submit  – Submit code for async analysis (returns immediately)
GET  /api/code/status/{job_id} – Poll job status
GET  /api/code/history/{user_id} – Recent submissions

Speed optimisations applied:
 • Background task returns job_id in < 100 ms
 • FAISS/embedding search is skipped when index is empty (saves 1-3 s)
 • Feature extraction + pattern lookup run concurrently with asyncio.gather
 • Code truncated to 2 000 chars before LLM to reduce token count / latency
 • max_tokens capped at 1 500 in llm_service (reduced prompt overhead)
 • analysis_time_ms logged for every job
"""
from __future__ import annotations
import asyncio
import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models.submission import Submission
from app.schemas.submission_schema import CodeSubmitRequest, JobStatusResponse
from app.services.preprocessing import extract_features
from app.services.llm_service import analyze_code
from rag import search_knowledge_base, get_kb_faiss_index
from app.services.pattern_service import update_patterns, get_top_concepts
from app.utils.helpers import generate_job_id, build_rag_query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/code", tags=["code"])

# Truncate code before sending to keep prompts small and fast
MAX_CODE_LEN = 2000


@router.post("/submit", response_model=JobStatusResponse, status_code=202)
async def submit_code(
    payload: CodeSubmitRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Returns job_id immediately (< 100 ms).
    Analysis runs in the background; poll status/{job_id} for results.
    """
    if not payload.code.strip():
        raise HTTPException(status_code=400, detail="Code cannot be empty.")
    if len(payload.code) > 50_000:
        raise HTTPException(status_code=400, detail="Code too long (max 50,000 chars).")

    job_id = generate_job_id()
    submission = Submission(
        id=job_id,
        user_id=payload.user_id,
        code=payload.code,
        language=payload.language,
        problem_description=payload.problem_description or "",
        status="processing",
    )
    db.add(submission)
    db.flush()

    background_tasks.add_task(
        _run_analysis,
        job_id=job_id,
        user_id=payload.user_id,
        code=payload.code,
        language=payload.language,
        problem_description=payload.problem_description or "",
    )

    return JobStatusResponse(
        job_id=job_id,
        status="processing",
        created_at=submission.created_at,
    )


@router.get("/status/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """Poll for completion of a code analysis job."""
    submission = db.query(Submission).filter(Submission.id == job_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Job not found.")

    return JobStatusResponse(
        job_id=submission.id,
        status=submission.status,
        feedback=submission.feedback if submission.status == "completed" else None,
        created_at=submission.created_at,
        completed_at=submission.completed_at,
    )


@router.get("/history/{user_id}")
def get_submission_history(user_id: str, limit: int = 10, db: Session = Depends(get_db)):
    """Return recent submissions for a user (without full feedback)."""
    submissions = (
        db.query(Submission)
        .filter(Submission.user_id == user_id)
        .order_by(Submission.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "user_id": user_id,
        "submissions": [
            {
                "job_id": s.id,
                "language": s.language,
                "status": s.status,
                "confidence_score": s.confidence_score,
                "created_at": s.created_at.isoformat(),
            }
            for s in submissions
        ],
    }


# ──────────────────────────────────────────────────────────────
# Background analysis worker — optimised for speed
# ──────────────────────────────────────────────────────────────

async def _run_analysis(
    job_id: str,
    user_id: str,
    code: str,
    language: str,
    problem_description: str,
) -> None:
    """RAG + LLM pipeline executed asynchronously in the background."""
    t_start = time.time()
    db = SessionLocal()
    try:
        # ── Step 1: Truncate code early to keep prompts small ──────
        if len(code) > MAX_CODE_LEN:
            logger.info("Job %s: truncating code %d→%d chars", job_id, len(code), MAX_CODE_LEN)
            code = code[:MAX_CODE_LEN]

        # ── Step 2: Feature extraction (fast, local, no API call) ──
        features = extract_features(code, language)
        logger.info("Job %s features: %s", job_id, features.get("suspected_concepts"))

        # ── Step 3: RAG + pattern lookup concurrently ───────────────
        # Skip FAISS embedding if index is empty (saves 1-3 s on empty KB)
        kb_index = get_kb_faiss_index()
        if kb_index.ntotal > 0:
            rag_query = build_rag_query(code, features, problem_description)
            # Run RAG search and pattern lookup concurrently
            kb_chunks_fut = asyncio.get_event_loop().run_in_executor(
                None, lambda: search_knowledge_base(rag_query, db, k=3)
            )
            top_concepts_fut = asyncio.get_event_loop().run_in_executor(
                None, lambda: get_top_concepts(db, user_id, limit=10)
            )
            kb_chunks, top = await asyncio.gather(kb_chunks_fut, top_concepts_fut)
        else:
            logger.info("Job %s: FAISS index empty — skipping RAG embedding call", job_id)
            kb_chunks = []
            top = get_top_concepts(db, user_id, limit=10)

        context = (
            "\n\n---\n\n".join(chunk.content for chunk in kb_chunks)
            if kb_chunks
            else "No relevant knowledge found."
        )
        rag_chunks_used = len(kb_chunks)
        rag_context_topics = list({chunk.topic for chunk in kb_chunks if chunk.topic})

        # ── Step 4: Recurring pattern check ────────────────────────
        known_concepts = {c["concept"] for c in top}
        suspected = set(features.get("suspected_concepts", []))
        is_recurring = bool(suspected & known_concepts)

        # ── Step 5: LLM analysis (async, non-blocking) ─────────────
        t_llm = time.time()
        feedback = await analyze_code(
            code=code,
            language=language,
            context=context,
            code_features=features,
            is_recurring=is_recurring,
        )
        logger.info(
            "Job %s: LLM finished in %.1f s (total so far %.1f s)",
            job_id,
            time.time() - t_llm,
            time.time() - t_start,
        )

        feedback["code_features"] = features
        feedback["rag_chunks_used"] = rag_chunks_used
        feedback["rag_context_topics"] = rag_context_topics

        # ── Step 6: Update error patterns ──────────────────────────
        concepts_detected = [e.get("concept", "general") for e in feedback.get("errors", [])]
        if concepts_detected:
            any_recurring = update_patterns(db, user_id, concepts_detected)
            feedback["is_recurring"] = feedback.get("is_recurring") or any_recurring

        # ── Step 7: Persist ─────────────────────────────────────────
        submission = db.query(Submission).filter(Submission.id == job_id).first()
        if submission:
            submission.status = "completed"
            submission.feedback = feedback
            submission.confidence_score = feedback.get("confidence_score", 0.0)
            submission.completed_at = datetime.now(timezone.utc)
        db.commit()

        total_s = time.time() - t_start
        logger.info(
            "✅ Job %s completed in %.1f s — confidence=%.0f%%, %d error(s)",
            job_id,
            total_s,
            (feedback.get("confidence_score", 0)) * 100,
            len(feedback.get("errors", [])),
        )

    except Exception as e:
        db.rollback()
        logger.error("Background analysis failed for job %s: %s", job_id, e, exc_info=True)
        # Mark job as failed with structured fallback
        db2 = SessionLocal()
        try:
            submission = db2.query(Submission).filter(Submission.id == job_id).first()
            if submission:
                submission.status = "failed"
                submission.feedback = {
                    "errors": [],
                    "overall_feedback": "AI analysis encountered an error — please try again.",
                    "concepts_to_study": [],
                    "confidence_score": 0.0,
                    "is_recurring": False,
                    "encouraging_message": "Don't give up! Please try submitting again. 🙂",
                }
                submission.completed_at = datetime.now(timezone.utc)
            db2.commit()
        except Exception:
            db2.rollback()
        finally:
            db2.close()
    finally:
        db.close()
