"""
app/main.py – FastAPI application entry point (synchronous PostgreSQL)
"""
from __future__ import annotations
import logging

# Load .env BEFORE any settings/config imports so all env vars are available
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass  # python-dotenv not installed; rely on shell env vars

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import engine, Base, create_tables
from app.routes import auth, code, feedback, roadmap, analytics, game, documents, ask

# ─────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


# ─────────────────────────────────────────────────────────────
# Create all DB tables on startup (sync, one-time)
# ─────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────
# Set up PGVector using SQLAlchemy on DB Engine Connection
# ─────────────────────────────────────────────────────────────
from app.models import user, submission, error_pattern, roadmap as roadmap_model, knowledge_document, knowledge_base, game_question  # noqa: F401, E402
Base.metadata.create_all(bind=engine)
logger.info("✅ Database tables ready.")

# Ensure FAISS index is synced with the DB
from rag import sync_faiss_index
from app.database import SessionLocal
try:
    with SessionLocal() as db:
        logger.info("Syncing FAISS index...")
        sync_faiss_index(db)
except Exception as e:
    logger.error(f"Failed to sync FAISS index: {e}")


# ─────────────────────────────────────────────────────────────
# Set up PGVector using SQLAlchemy on DB Engine Connection
# ─────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────
# FastAPI App
# ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="CodeMentor AI API",
    description=(
        "AI-powered code review backend with RAG pipeline, "
        "Error DNA tracking, personalized roadmap generation, and coding games."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# ─────────────────────────────────────────────────────────────
# CORS – allow React Vite frontend
# ─────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(code.router)
app.include_router(feedback.router)
app.include_router(roadmap.router)
app.include_router(analytics.router)
app.include_router(game.router)
app.include_router(documents.router)
app.include_router(ask.router, prefix="/api")

# ─────────────────────────────────────────────────────────────
# Root + Health Check
# ─────────────────────────────────────────────────────────────
@app.get("/", tags=["health"])
def root():
    return {
        "service": "CodeMentor AI API",
        "version": "1.0.0",
        "status": "running",
        "database": "postgresql",
        "docs": "/docs",
    }


@app.get("/health", tags=["health"])
def health():
    try:
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": str(e)}


# ─────────────────────────────────────────────────────────────
# Global Exception Handler
# ─────────────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
