"""
app/dashboard.py
────────────────
Admin dashboard helper routes (stats endpoint).
Intended as a placeholder for a future admin UI backend.
"""

from fastapi import APIRouter
from app.database import get_collection, get_log_collection
from app.models import DashboardStats

router = APIRouter(prefix="/dashboard", tags=["Admin Dashboard"])


@router.get("/stats", response_model=DashboardStats, summary="Dashboard statistics")
async def get_stats() -> DashboardStats:
    """
    Returns aggregate statistics for the admin dashboard:
    - Total distinct source documents ingested
    - Total number of chunks in the vector store
    - Number of queries logged in the last 24 hours
    """
    col = get_collection()
    log_col = get_log_collection()

    total_chunks: int = col.count_documents({})
    total_documents: int = len(col.distinct("source"))

    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_queries: int = log_col.count_documents(
        {"timestamp": {"$gte": cutoff.isoformat()}}
    )

    return DashboardStats(
        total_documents=total_documents,
        total_chunks=total_chunks,
        recent_queries=recent_queries,
    )
