"""
scripts/create_vector_index.py
──────────────────────────────
One-time script to create the Atlas Vector Search index on the
`embedding` field of the document_chunks collection.

Run this ONCE before ingesting any documents:
    python scripts/create_vector_index.py

Prerequisites:
  - MongoDB Atlas cluster with Vector Search enabled (M10+)
  - .env file configured with MONGODB_URI and DB_NAME
"""

import sys
import os
import certifi

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from pymongo import MongoClient
from app.config import settings

INDEX_NAME = "vector_index"
FIELD_PATH = "embedding"
NUM_DIMENSIONS = settings.EMBEDDING_DIMENSIONS  # 768 for text-embedding-004
SIMILARITY = "cosine"


def create_vector_index() -> None:
    from pymongo.operations import SearchIndexModel

    print(f"Connecting to MongoDB Atlas: {settings.MONGODB_URI[:40]}…")
    client = MongoClient(settings.MONGODB_URI, tlsCAFile=certifi.where())
    db = client[settings.DB_NAME]

    # ── Ensure the collection exists ─────────────────────────────────────────
    # Atlas requires the collection to physically exist before a search index
    # can be created on it. We create it explicitly if it's not there yet.
    existing_collections = db.list_collection_names()
    if settings.COLLECTION_NAME not in existing_collections:
        print(
            f"  Collection '{settings.COLLECTION_NAME}' does not exist yet — "
            "creating it now…"
        )
        # Insert a placeholder document, then delete it so the collection exists
        # but is logically empty.
        db.create_collection(settings.COLLECTION_NAME)
        print(f"  ✓ Collection '{settings.COLLECTION_NAME}' created.")
    else:
        print(f"  ✓ Collection '{settings.COLLECTION_NAME}' already exists.")

    collection = db[settings.COLLECTION_NAME]

    # ── Check if index already exists ────────────────────────────────────────
    try:
        existing = list(collection.list_search_indexes())
        existing_names = [idx.get("name") for idx in existing]
    except Exception:
        existing_names = []

    if INDEX_NAME in existing_names:
        print(f"✓ Vector index '{INDEX_NAME}' already exists. Nothing to do.")
        client.close()
        return

    # ── Define the vector search index ───────────────────────────────────────
    index_definition = {
        "mappings": {
            "dynamic": False,
            "fields": {
                FIELD_PATH: {
                    "type": "knnVector",
                    "dimensions": NUM_DIMENSIONS,
                    "similarity": SIMILARITY,
                }
            },
        }
    }

    print(f"Creating vector search index '{INDEX_NAME}'…")
    print(f"  Collection  : {settings.DB_NAME}.{settings.COLLECTION_NAME}")
    print(f"  Field       : {FIELD_PATH}")
    print(f"  Dimensions  : {NUM_DIMENSIONS}")
    print(f"  Similarity  : {SIMILARITY}")

    # Use SearchIndexModel (pymongo >= 4.7 recommended API)
    search_index_model = SearchIndexModel(
        definition=index_definition,
        name=INDEX_NAME,
    )
    collection.create_search_index(model=search_index_model)

    print(
        f"\n✓ Index creation request submitted successfully!\n"
        f"  Atlas typically takes 30–60 seconds to build the index.\n"
        f"  Check your Atlas UI → Search Indexes to confirm status = 'Active'."
    )
    client.close()


if __name__ == "__main__":
    create_vector_index()
