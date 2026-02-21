"""
app/database.py
───────────────
MongoDB Atlas connection & collection helpers.
Uses bare MongoClient(uri) — same pattern proven in scripts/create_vector_index.py.
"""

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from app.config import settings

# ── Module-level singleton (no lru_cache to avoid caching a broken connection) ─
_client: MongoClient | None = None


def _get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(settings.MONGODB_URI)
    return _client


def get_db() -> Database:
    return _get_client()[settings.DB_NAME]


def get_collection() -> Collection:
    """Return the document-chunk collection."""
    return get_db()[settings.COLLECTION_NAME]


def get_log_collection() -> Collection:
    """Return the query-log collection."""
    return get_db()[settings.LOG_COLLECTION]


# ── Admin helpers ─────────────────────────────────────────────────────────────

def list_documents() -> list[dict]:
    """
    Return one record per distinct source document:
      { source, chunk_count, uploaded_at }
    """
    col = get_collection()
    pipeline = [
        {
            "$group": {
                "_id": "$source",
                "chunk_count": {"$sum": 1},
                "uploaded_at": {"$max": "$uploaded_at"},
            }
        },
        {"$sort": {"_id": 1}},
    ]
    return list(col.aggregate(pipeline))


def delete_document(filename: str) -> int:
    """Delete all chunks belonging to `filename`. Returns deleted count."""
    col = get_collection()
    result = col.delete_many({"source": filename})
    return result.deleted_count


def document_exists(filename: str) -> bool:
    """Check whether any chunk exists for the given source filename."""
    col = get_collection()
    return col.count_documents({"source": filename}, limit=1) > 0
