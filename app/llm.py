"""
app/llm.py
──────────
Gemini 2.5 Flash generation layer with:
  - Strict system prompt (cite sources, no fabrication)
  - Prompt construction from retrieved chunks
  - Citation extraction + guardrail (regenerate once if no citations found)
Uses google.genai SDK.
"""

import logging
import re
from dataclasses import dataclass

from google import genai
from google.genai import types

from app.config import settings
from app.models import Citation

logger = logging.getLogger(__name__)

# ── Gemini client (singleton) ────────────────────────────────────────────────
_client = genai.Client(api_key=settings.GEMINI_API_KEY)

# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are OpsMind AI, an enterprise knowledge assistant.
You must answer strictly using the provided context.
You must cite page number and source filename for every claim you make.
Use the format: [Source: <filename>, Page: <number>]
If the answer is not explicitly found in the context, respond with exactly:
"I don't know based on the available documents."
Never fabricate information. Never use external knowledge."""

# ── Fallback ──────────────────────────────────────────────────────────────────
FALLBACK_ANSWER = "I don't know based on the available documents."

# ── Citation regex ────────────────────────────────────────────────────────────
_CITATION_RE = re.compile(
    r"\[Source:\s*(?P<source>[^\]]+?),\s*Page:\s*(?P<page>\d+)\]",
    re.IGNORECASE,
)


@dataclass
class LLMResult:
    answer: str
    citations: list[Citation]
    confidence_score: float
    retrieved_chunks: int


def _build_context_block(chunks: list[dict]) -> str:
    """Format retrieved chunks into a numbered context block."""
    parts = []
    for i, chunk in enumerate(chunks, start=1):
        parts.append(
            f"[{i}] Source: {chunk['source']}, Page: {chunk['page_number']}\n"
            f"{chunk['text']}"
        )
    return "\n\n".join(parts)


def _parse_citations(text: str) -> list[Citation]:
    """Extract citations from the model's response text."""
    seen: set[tuple[str, int]] = set()
    citations: list[Citation] = []
    for m in _CITATION_RE.finditer(text):
        source = m.group("source").strip()
        page = int(m.group("page"))
        key = (source, page)
        if key not in seen:
            seen.add(key)
            citations.append(Citation(source=source, page=page))
    return citations


def _has_citations(text: str) -> bool:
    return bool(_CITATION_RE.search(text))


def _generate(prompt: str) -> str:
    """Call the LLM and return raw response text. Retries on 429 rate limits."""
    import time
    from google.genai.errors import ClientError

    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            response = _client.models.generate_content(
                model=settings.LLM_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                ),
            )
            return response.text.strip()
        except ClientError as e:
            is_rate_limit = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)
            if is_rate_limit and attempt < max_retries:
                wait = (attempt + 1) * 10  # 10s, 20s
                logger.warning("Rate limited, retrying in %ds (attempt %d/%d)", wait, attempt + 1, max_retries)
                time.sleep(wait)
            elif is_rate_limit:
                raise RuntimeError(
                    "Gemini API rate limit exceeded. Your free-tier daily quota is exhausted. "
                    "Please wait a few minutes and try again, or upgrade to a paid plan at "
                    "https://ai.google.dev/pricing"
                )
            else:
                raise


def generate_answer(question: str, chunks: list[dict]) -> LLMResult:
    """
    Generate an answer from retrieved chunks.

    Guardrails:
      1. If no chunks → fallback immediately.
      2. Build prompt and call Gemini.
      3. If response has no citations → regenerate once with explicit instruction.
      4. If still no citations → return fallback.
    """
    if not chunks:
        logger.warning("No chunks provided to LLM — returning fallback.")
        return LLMResult(
            answer=FALLBACK_ANSWER,
            citations=[],
            confidence_score=0.0,
            retrieved_chunks=0,
        )

    context_block = _build_context_block(chunks)
    prompt = (
        f"Context:\n{context_block}\n\n"
        f"Question:\n{question}"
    )

    # ── First generation attempt ──────────────────────────────────────────
    answer = _generate(prompt)
    logger.info("First generation attempt completed.")

    # ── Guardrail: check for citations ────────────────────────────────────
    if not _has_citations(answer):
        logger.warning("No citations found — regenerating with explicit instruction.")
        regen_prompt = (
            f"Context:\n{context_block}\n\n"
            f"Question:\n{question}\n\n"
            "IMPORTANT: Your previous response lacked citations. "
            "You MUST cite every claim using the format: "
            "[Source: <filename>, Page: <number>]. "
            "If you cannot cite from the context, respond with: "
            f'"{FALLBACK_ANSWER}"'
        )
        answer = _generate(regen_prompt)
        logger.info("Regeneration attempt completed.")

        if not _has_citations(answer):
            logger.warning("Regeneration still produced no citations — returning fallback.")
            return LLMResult(
                answer=FALLBACK_ANSWER,
                citations=[],
                confidence_score=0.0,
                retrieved_chunks=len(chunks),
            )

    citations = _parse_citations(answer)
    scores = [c.get("score", 0.0) for c in chunks]
    confidence_score = round(sum(scores) / len(scores), 4) if scores else 0.0

    return LLMResult(
        answer=answer,
        citations=citations,
        confidence_score=confidence_score,
        retrieved_chunks=len(chunks),
    )
