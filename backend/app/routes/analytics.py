"""routes/analytics.py – User performance analytics dashboard (sync)"""
from __future__ import annotations
import logging

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.submission import Submission
from app.services.pattern_service import get_concept_breakdown, get_top_concepts
from app.utils.helpers import calculate_streak, calculate_improvement

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/{user_id}")
def get_analytics(user_id: str, db: Session = Depends(get_db)):
    """Full analytics dashboard — queries live database data."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    submissions = (
        db.query(Submission)
        .filter(Submission.user_id == user_id)
        .order_by(Submission.created_at.asc())
        .all()
    )

    concept_breakdown = get_concept_breakdown(db, user_id)
    streak = calculate_streak(submissions)
    improvement = calculate_improvement(submissions)

    total_subs = len(submissions)
    completed = [s for s in submissions if s.status == "completed"]

    if total_subs > 0:
        accuracy_rate = len(completed) / total_subs * 100
        conf_values = [s.confidence_score for s in completed if s.confidence_score]
        difficulty_proxy = (sum(conf_values) / len(conf_values)) if conf_values else 50.0
    else:
        accuracy_rate = 0.0
        difficulty_proxy = 0.0

    consistency_score = min(streak * 10, 100)
    placement_readiness = (accuracy_rate * 0.4) + (difficulty_proxy * 0.3) + (consistency_score * 0.3)

    user.streak = streak
    user.placement_readiness = placement_readiness
    db.flush()

    score_trend = [
        {"submission": idx, "score": round((s.confidence_score or 0.0) * 100)}
        for idx, s in enumerate(submissions, start=1)
    ]

    error_dna = [
        {"concept": concept.replace("_", " "), "count": count}
        for concept, count in concept_breakdown.items()
    ]

    avg_confidence = round(
        sum(s.confidence_score or 0 for s in completed) / len(completed) * 100
    ) if completed else 0

    return {
        "streak": streak,
        "submissions": total_subs,
        "completed": len(completed),
        "improvement": round(improvement),
        "placement_readiness": round(placement_readiness),
        "avg_confidence": avg_confidence,
        "score_trend": score_trend,
        "error_dna": error_dna,
    }


@router.get("/error-patterns/{user_id}")
def get_error_patterns(user_id: str, db: Session = Depends(get_db)):
    """Detailed error DNA breakdown from real submission data."""
    breakdown = get_concept_breakdown(db, user_id)
    top = get_top_concepts(db, user_id, limit=10)
    total_errors = sum(breakdown.values())
    enriched = []
    for item in top:
        pct = round((item["frequency"] / total_errors * 100), 1) if total_errors else 0
        enriched.append({**item, "percent": pct})
    return {"user_id": user_id, "total_errors": total_errors, "breakdown": enriched}