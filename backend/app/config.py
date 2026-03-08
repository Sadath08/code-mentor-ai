"""
config.py – App settings loaded from .env
"""
from __future__ import annotations
from typing import List
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── OpenAI ──────────────────────────────────────────────────
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # ── Groq (Llama-3) ──────────────────────────────────────────
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # ── Gemini (free-tier fallback) ──────────────────────────────
    gemini_api_key: str = ""
    gemini_model: str = "models/gemini-2.0-flash"

    # ── Embedding model ──────────────────────────────────────────
    embedding_model: str = "models/embedding-001"

    # ── Shared ──────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./codementor.db"
    faiss_index_path: str = "./knowledge_base/faiss_index"
    user_faiss_index_path: str = "./knowledge_base/user_faiss_index"
    secret_key: str = "changeme-use-a-real-secret-32chars"

    # ── Provider detection ───────────────────────────────────────
    @property
    def use_openai(self) -> bool:
        key = self.openai_api_key.strip()
        return bool(key) and key.startswith("sk-")

    @property
    def use_groq(self) -> bool:
        key = self.groq_api_key.strip()
        return bool(key) and key.startswith("gsk_")

    @property
    def use_gemini(self) -> bool:
        return bool(self.gemini_api_key.strip())

    # CORS origins for React frontend
    cors_origins: List[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
    ]

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
