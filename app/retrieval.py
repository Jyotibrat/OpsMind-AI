"""
app/retrieval.py
────────────────
Vector search against MongoDB Atlas using cosine similarity.
Filters out results below SIMILARITY_THRESHOLD.
Uses google.genai SDK for embeddings.
"""

import logging

from google import genai
from google.genai import types

from app.config import settings
from app.database import get_collection

logger = logging.getLogger(__name__)

# ── Gemini client (singleton) ────────────────────────────────────────────────
_client = genai.Client(api_key=settings.GEMINI_API_KEY)


def _embed_query(query: str) -> list[float]:
    """Embed the user query with RETRIEVAL_QUERY task type."""
    result = _client.models.embed_content(
        model=settings.EMBEDDING_MODEL,
        contents=query,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=settings.EMBEDDING_DIMENSIONS,  # must match stored vectors
        ),
    )
    return result.embeddings[0].values


def retrieve_chunks(question: str) -> list[dict]:
    """
    Embed the question and run MongoDB Atlas $vectorSearch.

    Returns a list of dicts:
      { text, source, page_number, score }
    Only includes chunks where score >= SIMILARITY_THRESHOLD.
    """
    query_embedding = _embed_query(question)
    collection = get_collection()

    pipeline = [
        {
            "$vectorSearch": {
                "index": settings.VECTOR_INDEX_NAME,
                "path": "embedding",
                "queryVector": query_embedding,
                "numCandidates": settings.TOP_K * 10,
                "limit": settings.TOP_K,
            }
        },
        {
            "$project": {
                "_id": 0,
                "text": 1,
                "source": 1,
                "page_number": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]

    raw_results = list(collection.aggregate(pipeline))

    # Log raw scores to help tune the threshold
    if raw_results:
        scores = [r.get('score', 0.0) for r in raw_results]
        logger.info(
            "Raw scores: %s (threshold: %.2f)",
            [round(s, 4) for s in scores],
            settings.SIMILARITY_THRESHOLD,
        )

    # Filter by similarity threshold
    filtered = [
        r for r in raw_results
        if r.get("score", 0.0) >= settings.SIMILARITY_THRESHOLD
    ]

    logger.info(
        "Vector search: %d raw results, %d above threshold %.2f",
        len(raw_results),
        len(filtered),
        settings.SIMILARITY_THRESHOLD,
    )

    return filtered
