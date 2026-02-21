"""
scripts/diagnose_search.py
Diagnostic script to test embedding + vector search pipeline end-to-end.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types
from pymongo import MongoClient
from app.config import settings


def diagnose():
    print("=" * 60)
    print("OpsMind AI - Search Diagnostics")
    print("=" * 60)

    print("\n[Config]")
    print(f"  EMBEDDING_MODEL      : {settings.EMBEDDING_MODEL}")
    print(f"  EMBEDDING_DIMENSIONS : {settings.EMBEDDING_DIMENSIONS}")
    print(f"  SIMILARITY_THRESHOLD : {settings.SIMILARITY_THRESHOLD}")
    print(f"  TOP_K                : {settings.TOP_K}")
    print(f"  DB_NAME              : {settings.DB_NAME}")
    print(f"  COLLECTION_NAME      : {settings.COLLECTION_NAME}")

    # 1. Check stored chunks
    print("\n[MongoDB Connection]")
    client = MongoClient(settings.MONGODB_URI)
    client.admin.command("ping")
    print("  OK - Connected to Atlas")

    db = client[settings.DB_NAME]
    col = db[settings.COLLECTION_NAME]
    count = col.count_documents({})
    print(f"  Total chunks in collection: {count}")

    if count == 0:
        print("  FAIL - No chunks found! Upload documents first.")
        return

    sample = col.find_one()
    emb = sample.get("embedding", [])
    src = sample.get("source", "?")
    print(f"  Sample source: {src}")
    print(f"  Stored embedding length: {len(emb)}")
    if emb:
        print(f"  Stored embedding first 3: {emb[:3]}")

    # 2. List search indexes
    print("\n[Atlas Search Indexes]")
    try:
        indexes = list(col.list_search_indexes())
        if not indexes:
            print("  FAIL - NO vector search indexes found!")
            print("  -> Run: python scripts/create_vector_index.py")
            return
        for idx in indexes:
            print(f"  Index: {idx.get('name')} | Status: {idx.get('status')} | Type: {idx.get('type')}")
            if idx.get("latestDefinition"):
                defn = idx["latestDefinition"]
                print(f"         Definition: {defn}")
    except Exception as e:
        print(f"  WARNING - Could not list indexes: {e}")

    # 3. Embed query
    print("\n[Query Embedding]")
    query = "Explain the code of conduct"
    print(f"  Query: '{query}'")

    gc = genai.Client(api_key=settings.GEMINI_API_KEY)
    result = gc.models.embed_content(
        model=settings.EMBEDDING_MODEL,
        contents=query,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=settings.EMBEDDING_DIMENSIONS,
        ),
    )
    qvec = result.embeddings[0].values
    print(f"  Query embedding length: {len(qvec)}")
    print(f"  Query embedding first 3: {qvec[:3]}")

    # 4. Run $vectorSearch
    print("\n[Vector Search Results]")
    pipeline = [
        {
            "$vectorSearch": {
                "index": settings.VECTOR_INDEX_NAME,
                "path": "embedding",
                "queryVector": qvec,
                "numCandidates": 50,
                "limit": 5,
            }
        },
        {
            "$project": {
                "_id": 0,
                "source": 1,
                "page_number": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]

    try:
        results = list(col.aggregate(pipeline))
    except Exception as e:
        print(f"  FAIL - Vector search error: {e}")
        print("  -> Check if the vector index is ACTIVE in Atlas UI")
        return

    if not results:
        print("  FAIL - $vectorSearch returned 0 results!")
        print("  Possible causes:")
        print("    1. Vector index is not ACTIVE yet (check Atlas UI)")
        print("    2. Index dimensions mismatch (index expects different dim)")
        print("    3. Index is on wrong field name")
        return

    for r in results:
        score = r.get("score", 0)
        tag = "PASS" if score >= settings.SIMILARITY_THRESHOLD else "BELOW"
        print(f"  [{tag}] score={score:.4f} | {r['source']} p.{r['page_number']}")

    above_threshold = [r for r in results if r.get("score", 0) >= settings.SIMILARITY_THRESHOLD]
    print(f"\n  {len(results)} total results, {len(above_threshold)} above threshold ({settings.SIMILARITY_THRESHOLD})")

    if not above_threshold:
        print("  -> Lower SIMILARITY_THRESHOLD in .env (try 0.3 or 0.4)")

    client.close()
    print("\n" + "=" * 60)
    print("Diagnostics complete.")


if __name__ == "__main__":
    diagnose()
