"""
app/config.py
─────────────
Loads and validates all environment variables via python-dotenv.
Import `settings` wherever configuration is needed.
"""

import os
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # ── Required ────────────────────────────────────────
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    MONGODB_URI: str = os.getenv("MONGODB_URI", "")

    # ── MongoDB ──────────────────────────────────────────
    DB_NAME: str = os.getenv("DB_NAME", "opsmind_ai")
    COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", "document_chunks")
    LOG_COLLECTION: str = os.getenv("LOG_COLLECTION", "query_logs")

    # ── RAG Tuning ───────────────────────────────────────
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.5"))
    TOP_K: int = int(os.getenv("TOP_K", "5"))
    VECTOR_INDEX_NAME: str = os.getenv("VECTOR_INDEX_NAME", "vector_index_1")

    # ── Auth ─────────────────────────────────────────────
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-to-a-random-secret-in-production")
    TOKEN_EXPIRE_HOURS: int = int(os.getenv("TOKEN_EXPIRE_HOURS", "8"))
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")
    EMPLOYEE_USERNAME: str = os.getenv("EMPLOYEE_USERNAME", "employee")
    EMPLOYEE_PASSWORD: str = os.getenv("EMPLOYEE_PASSWORD", "employee123")

    # ── Models ───────────────────────────────────────────
    # Current model names per https://ai.google.dev/gemini-api/docs/embeddings
    EMBEDDING_MODEL: str = "gemini-embedding-001"   # supports 128-3072 dims
    EMBEDDING_DIMENSIONS: int = 768
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-2.5-flash")

    # ── Chunking ─────────────────────────────────────────
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    # ── Paths ────────────────────────────────────────────
    DOCS_DIR: str = "docs"
    LOGS_DIR: str = "logs"

    def validate(self) -> None:
        """Raise on startup if critical env vars are missing."""
        missing = []
        if not self.GEMINI_API_KEY:
            missing.append("GEMINI_API_KEY")
        if not self.MONGODB_URI:
            missing.append("MONGODB_URI")
        if missing:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(missing)}. "
                "Copy .env.example to .env and fill in your values."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.validate()
    return s


settings: Settings = Settings()  # module-level convenience alias
