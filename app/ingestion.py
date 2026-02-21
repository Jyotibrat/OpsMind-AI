"""
app/ingestion.py
────────────────
PDF ingestion pipeline:
  1. Parse PDF with PyMuPDF (page-by-page, preserving page numbers)
  2. Chunk text with a custom RecursiveCharacterTextSplitter (no external deps)
  3. Embed each chunk with Gemini text-embedding-004 via google.genai
  4. Upsert chunks into MongoDB Atlas
"""

import logging
import re
from datetime import datetime, timezone

import fitz  # PyMuPDF
from google import genai
from google.genai import types

from app.config import settings
from app.database import get_collection, delete_document

logger = logging.getLogger(__name__)

# ── Gemini client (singleton) ────────────────────────────────────────────────
# gemini-embedding-001 uses v1beta (SDK default) per official docs
_client = genai.Client(api_key=settings.GEMINI_API_KEY)



# ── Minimal RecursiveCharacterTextSplitter (no NLTK / langchain needed) ──────
class _RecursiveTextSplitter:
    """
    Pure-Python recursive character splitter that mirrors the behaviour of
    LangChain's RecursiveCharacterTextSplitter.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: list[str] | None = None,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", " ", ""]

    def split_text(self, text: str) -> list[str]:
        return self._split(text, self.separators)

    def _split(self, text: str, separators: list[str]) -> list[str]:
        if len(text) <= self.chunk_size:
            return [text] if text.strip() else []

        # Pick first separator that actually appears in the text
        sep = ""
        remaining = list(separators)
        for s in separators:
            if s == "" or s in text:
                sep = s
                remaining = separators[separators.index(s) + 1 :]
                break

        parts = text.split(sep) if sep else list(text)
        chunks: list[str] = []
        current = ""

        for part in parts:
            candidate = (current + sep + part) if current else part
            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                if current.strip():
                    chunks.append(current)
                # If single part is still too big, recurse with next separator
                if len(part) > self.chunk_size:
                    chunks.extend(self._split(part, remaining))
                    current = ""
                else:
                    current = part

        if current.strip():
            chunks.append(current)

        # Apply overlap by merging adjacent chunks
        return self._apply_overlap(chunks)

    def _apply_overlap(self, chunks: list[str]) -> list[str]:
        if self.chunk_overlap <= 0 or len(chunks) <= 1:
            return chunks

        merged: list[str] = [chunks[0]]
        for chunk in chunks[1:]:
            prev = merged[-1]
            # Take last `chunk_overlap` chars of previous chunk as prefix
            overlap_prefix = prev[-self.chunk_overlap :] if len(prev) > self.chunk_overlap else prev
            candidate = overlap_prefix + " " + chunk
            if len(candidate) <= self.chunk_size:
                # Keep original chunk (overlap is just for context continuity)
                merged.append(chunk)
            else:
                merged.append(chunk)
        return merged


_splitter = _RecursiveTextSplitter(
    chunk_size=settings.CHUNK_SIZE,
    chunk_overlap=settings.CHUNK_OVERLAP,
)


# ── Embedding ────────────────────────────────────────────────────────────────
def _embed_texts(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """
    Embed a list of texts using gemini-embedding-001.
    Processes in batches of 100 to respect API limits.
    Returns list of 768-dimensional embedding vectors.
    """
    embeddings: list[list[float]] = []
    batch_size = 100

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        result = _client.models.embed_content(
            model=settings.EMBEDDING_MODEL,
            contents=batch,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=settings.EMBEDDING_DIMENSIONS,  # pin to 768
            ),
        )
        # result.embeddings is a list of ContentEmbedding objects with .values
        embeddings.extend([e.values for e in result.embeddings])

    return embeddings


# ── Ingestion Pipeline ────────────────────────────────────────────────────────
def ingest_pdf(
    file_bytes: bytes,
    filename: str,
    overwrite: bool = True,
) -> int:
    """
    Full ingestion pipeline for a single PDF.

    Args:
        file_bytes: Raw PDF bytes.
        filename:   Original filename (used as `source` in MongoDB).
        overwrite:  If True, delete existing chunks before re-ingesting.

    Returns:
        Number of chunks inserted into MongoDB.
    """
    if not filename.lower().endswith(".pdf"):
        raise ValueError(f"'{filename}' is not a PDF file.")

    if overwrite:
        deleted = delete_document(filename)
        if deleted:
            logger.info("Deleted %d existing chunks for '%s'.", deleted, filename)

    # ── 1. Parse PDF ────────────────────────────────────────────────────────
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages_text: list[tuple[int, str]] = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text = page.get_text("text").strip()
        if text:
            pages_text.append((page_num + 1, text))  # 1-indexed

    doc.close()

    if not pages_text:
        raise ValueError(f"No extractable text found in '{filename}'.")

    logger.info("Parsed %d pages from '%s'.", len(pages_text), filename)

    # ── 2. Chunk ─────────────────────────────────────────────────────────────
    chunk_records: list[dict] = []
    for page_number, page_text in pages_text:
        for chunk_text in _splitter.split_text(page_text):
            if chunk_text.strip():
                chunk_records.append(
                    {
                        "text": chunk_text,
                        "page_number": page_number,
                        "source": filename,
                    }
                )

    if not chunk_records:
        raise ValueError(f"Chunking produced no content for '{filename}'.")

    logger.info("Created %d chunks from '%s'.", len(chunk_records), filename)

    # ── 3. Embed ─────────────────────────────────────────────────────────────
    texts_to_embed = [r["text"] for r in chunk_records]
    embeddings = _embed_texts(texts_to_embed, task_type="RETRIEVAL_DOCUMENT")

    now = datetime.now(timezone.utc)
    for record, embedding in zip(chunk_records, embeddings):
        record["embedding"] = embedding
        record["uploaded_at"] = now

    # ── 4. Store in MongoDB ─────────────────────────────────────────────────
    collection = get_collection()
    result = collection.insert_many(chunk_records)
    inserted_count = len(result.inserted_ids)

    logger.info("Inserted %d chunks for '%s' into MongoDB.", inserted_count, filename)
    return inserted_count
