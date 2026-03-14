"""
app/logger.py
─────────────
Logs all queries and their retrieved chunks to MongoDB (query_logs collection)
and optionally to a local JSONL file for offline analysis.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.database import get_log_collection

_file_logger = logging.getLogger(__name__)

# Ensure logs directory exists if filesystem is writable (Vercel runtime is read-only).
_LOG_FILE = None
try:
    Path(settings.LOGS_DIR).mkdir(parents=True, exist_ok=True)
    _LOG_FILE = Path(settings.LOGS_DIR) / "queries.jsonl"
except PermissionError as exc:
    _file_logger.warning(
        "Local log directory '%s' is not writable (likely read-only filesystem on serverless). "
        "File logging will be disabled. Error: %s",
        settings.LOGS_DIR,
        exc,
    )
    _LOG_FILE = None
except OSError as exc:
    # Some environments return EROFS via OSError.
    if exc.errno == 30:
        _file_logger.warning(
            "Local log directory '%s' is not writable (read-only filesystem). "
            "File logging will be disabled. Error: %s",
            settings.LOGS_DIR,
            exc,
        )
        _LOG_FILE = None
    else:
        raise


def log_query(
    question: str,
    chunks: list[dict],
    answer: str,
    citations: list,
    confidence_score: float,
) -> None:
    """
    Persist a query log entry to:
      1. MongoDB `query_logs` collection
      2. Local `logs/queries.jsonl` file
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "retrieved_chunks": [
            {
                "source": c.get("source"),
                "page_number": c.get("page_number"),
                "score": round(c.get("score", 0.0), 4),
                "text_preview": c.get("text", "")[:200],
            }
            for c in chunks
        ],
        "answer_preview": answer[:500],
        "citations": [
            {"source": cit.source, "page": cit.page} for cit in citations
        ],
        "confidence_score": confidence_score,
    }

    # ── MongoDB ──────────────────────────────────────────────────────────────
    try:
        get_log_collection().insert_one(entry.copy())
    except Exception as exc:  # noqa: BLE001
        _file_logger.error("Failed to write query log to MongoDB: %s", exc)

    # ── Local JSONL ──────────────────────────────────────────────────────────
    if _LOG_FILE is None:
        return

    try:
        with _LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:  # noqa: BLE001
        _file_logger.error("Failed to write query log to file: %s", exc)
