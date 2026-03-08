"""
seed_db.py
----------
Populate the PostgreSQL database with demo data for the CodeMentor AI hackathon.
Creates a test user, mock submissions, and error patterns.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app.models.user import User
from app.models.submission import Submission
from app.models.error_pattern import ErrorPattern
from app.utils.helpers import hash_password, generate_job_id

def seed():
    print("⏳ Seeding database...")
    
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    
    try:
        # 1. Create Demo User
        demo_email = "arjun@example.com"
        existing_user = db.query(User).filter(User.email == demo_email).first()
        
        if existing_user:
            print(f"ℹ️ User {demo_email} already exists. Skipping user creation.")
            user = existing_user
        else:
            user = User(
                id="user_arjun_123",
                name="Arjun Sharma",
                email=demo_email,
                college="State Tech University",
                hashed_password=hash_password("password123"),
                skill_level="intermediate",
                goal="placement",
                streak=5,
                placement_readiness=67.5,
                created_at=datetime.now(timezone.utc) - timedelta(days=30)
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"✅ Created user: {user.name}")

        # 2. Add Mock Error Patterns (Error DNA)
        patterns = [
            {"concept": "loops", "frequency": 12, "last_seen": datetime.now(timezone.utc) - timedelta(hours=2)},
            {"concept": "recursion", "frequency": 8, "last_seen": datetime.now(timezone.utc) - timedelta(days=1)},
            {"concept": "syntax_error", "frequency": 15, "last_seen": datetime.now(timezone.utc) - timedelta(minutes=30)},
            {"concept": "naming_issue", "frequency": 4, "last_seen": datetime.now(timezone.utc) - timedelta(days=3)},
        ]
        
        for p in patterns:
            existing_p = db.query(ErrorPattern).filter(
                ErrorPattern.user_id == user.id, 
                ErrorPattern.concept == p["concept"]
            ).first()
            
            if existing_p:
                existing_p.frequency = p["frequency"]
                existing_p.last_seen = p["last_seen"]
            else:
                db.add(ErrorPattern(
                    user_id=user.id,
                    concept=p["concept"],
                    frequency=p["frequency"],
                    last_seen=p["last_seen"]
                ))
        print("✅ Seeded Error DNA patterns.")

        # 3. Add Mock Submissions
        test_submissions = [
            {
                "id": "sub_1",
                "code": "def find_max(arr):\n    m = arr[0]\n    for i in range(len(arr) + 1):\n        if arr[i] > m: m = arr[i]\n    return m",
                "feedback": {
                    "errors": [{"line": 3, "type": "logic_error", "concept": "loops", "what": "Index out of range", "why": "range(len(arr)+1) visits index len(arr)", "fix": "use range(len(arr))"}],
                    "confidence_score": 0.4
                },
                "status": "completed",
                "created_at": datetime.now(timezone.utc) - timedelta(days=4)
            },
            {
                "id": "sub_2",
                "code": "def factorial(n):\n    if n == 0: return 0\n    return n * factorial(n-1)",
                "feedback": {
                    "errors": [{"line": 2, "type": "logic_error", "concept": "recursion", "what": "Infinite recursion for n>0", "why": "Base case returns 0, logic results in 0", "fix": "Base case should return 1 for n=0"}],
                    "confidence_score": 0.6
                },
                "status": "completed",
                "created_at": datetime.now(timezone.utc) - timedelta(days=2)
            },
             {
                "id": "sub_3",
                "code": "def sum_list(l):\n    s = 0\n    for x in l: s += x\n    return s",
                "feedback": {
                    "errors": [],
                    "overall_feedback": "Perfect implementation of list summation.",
                    "confidence_score": 1.0
                },
                "status": "completed",
                "created_at": datetime.now(timezone.utc) - timedelta(hours=5)
            }
        ]

        for s_data in test_submissions:
            existing_s = db.query(Submission).filter(Submission.id == s_data["id"]).first()
            if not existing_s:
                sub = Submission(
                    id=s_data["id"],
                    user_id=user.id,
                    code=s_data["code"],
                    language="python",
                    status=s_data["status"],
                    feedback=s_data["feedback"],
                    confidence_score=s_data["feedback"]["confidence_score"],
                    created_at=s_data["created_at"],
                    completed_at=s_data["created_at"] + timedelta(seconds=15)
                )
                db.add(sub)
        
        db.commit()
        print("✅ Seeded mock submissions.")
        print("\n🚀 Database Seeding Complete!")
        print(f"Login with: arjun@example.com / password123")

    except Exception as e:
        db.rollback()
        print(f"❌ Seeding failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
