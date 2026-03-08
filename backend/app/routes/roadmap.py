"""routes/roadmap.py – Get/regenerate personalized roadmap with placement metadata"""
from __future__ import annotations
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.submission import Submission
from app.services.roadmap_service import generate_roadmap, get_latest_roadmap
from app.services.pattern_service import get_top_concepts
from app.utils.helpers import calculate_streak

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/roadmap", tags=["roadmap"])


def _compute_placement_score(db: Session, user_id: str, weeks: list, current_week: int) -> int:
    """
    Placement score 0-100:
    • 40 pts from roadmap progress (current_week / total_weeks * 40)
    • 30 pts from submission volume (capped at 20 submissions → 30 pts)
    • 20 pts from error pattern diversity (more concepts fixed → higher score)
    • 10 pts streak bonus
    """
    total = len(weeks)
    progress_score = int((current_week / max(total, 1)) * 40)

    sub_count = db.query(Submission).filter(Submission.user_id == user_id).count()
    submission_score = min(sub_count * 2, 30)  # 2 pts per submission, max 30

    concepts = get_top_concepts(db, user_id, limit=10)
    concept_score = min(len(concepts) * 4, 20)  # 4 pts per concept, max 20

    subs = db.query(Submission).filter(Submission.user_id == user_id).all()
    streak = calculate_streak(subs)
    streak_score = min(streak * 1, 10)  # 1 pt per day streak, max 10

    return min(progress_score + submission_score + concept_score + streak_score, 100)


@router.get("/{user_id}")
async def get_roadmap(
    user_id: str,
    regenerate: bool = Query(False, description="Force regeneration of the roadmap"),
    db: Session = Depends(get_db),
):
    """
    Return the user's learning roadmap with placement metadata.
    Response includes:
      placement_score, current_week, completion_pct, weeks, cached
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Try to serve from cache
    roadmap_data = None
    cached = False
    if not regenerate:
        roadmap_data = get_latest_roadmap(db, user_id)
        if roadmap_data:
            cached = True

    # Generate if cache miss or forced
    if not roadmap_data:
        roadmap_data = await generate_roadmap(db, user_id, user.skill_level, user.goal)
        db.commit()

    weeks = roadmap_data.get("weeks", [])
    total_weeks = len(weeks)

    # Derive current_week from submission count (1 submission per week threshold)
    sub_count = db.query(Submission).filter(Submission.user_id == user_id).count()
    current_week = min(max(sub_count // 2, 0), total_weeks - 1) if total_weeks > 0 else 0
    completion_pct = round((current_week / max(total_weeks, 1)) * 100)

    placement_score = _compute_placement_score(db, user_id, weeks, current_week)

    # Streak
    subs = db.query(Submission).filter(Submission.user_id == user_id).all()
    streak = calculate_streak(subs)

    return {
        "user_id": user_id,
        "roadmap": roadmap_data,
        "placement_score": placement_score,
        "current_week": current_week,
        "total_weeks": total_weeks,
        "completion_pct": completion_pct,
        "streak": streak,
        "cached": cached,
    }
