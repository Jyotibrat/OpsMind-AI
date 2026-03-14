"""
app/main.py
───────────
FastAPI application entrypoint.
Auth-protected routes:
  - POST /auth/login         → public
  - GET  /auth/me            → any authenticated user
  - POST /ask                → any authenticated user (admin + employee)
  - POST /upload-documents   → admin only
  - GET  /list-documents     → admin only
  - DELETE /delete-document  → admin only
  - GET  /dashboard/stats    → admin only
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.auth import (
    authenticate_user,
    create_access_token,
    require_admin,
    require_any_role,
    seed_default_users,
)
from app.config import settings
from app.dashboard import router as dashboard_router
from app.database import delete_document, document_exists, list_documents
from app.ingestion import ingest_pdf
from app.llm import FALLBACK_ANSWER, generate_answer
from app.logger import log_query
from app.models import (
    AskRequest,
    AskResponse,
    DeleteResponse,
    DocumentInfo,
    DocumentListResponse,
    HealthResponse,
    LoginRequest,
    TokenResponse,
    UploadResponse,
    UserInfo,
)
from app.retrieval import retrieve_chunks

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("OpsMind AI starting up…")
    settings.validate()
    try:
        seed_default_users()   # Ensure default admin + employee exist
    except Exception as exc:
        logger.warning(
            "Could not seed default users on startup (will retry on first login): %s", exc
        )
    yield
    logger.info("OpsMind AI shutting down.")



# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="OpsMind AI",
    description=(
        "Production-ready RAG system for enterprise document Q&A. "
        "Powered by Gemini 2.5 Flash + MongoDB Atlas Vector Search."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(dashboard_router)


# ════════════════════════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ════════════════════════════════════════════════════════════════════════════════

@app.post(
    "/auth/login",
    response_model=TokenResponse,
    tags=["Auth"],
    summary="Login and receive a JWT",
)
async def login(request: LoginRequest) -> TokenResponse:
    """
    Authenticate with username + password.
    Returns a JWT that must be sent as `Authorization: Bearer <token>`
    on all subsequent requests.
    """
    # Lazy seed: if startup seeding was skipped (mongo slow), try now
    try:
        seed_default_users()
    except Exception:
        pass  # Already seeded or DB still unavailable; authenticate_user will raise its own error

    user = authenticate_user(request.username, request.password)
    token = create_access_token(
        username=user["username"],
        role=user["role"],
        display_name=user.get("display_name", user["username"]),
    )
    return TokenResponse(
        access_token=token,
        role=user["role"],
        display_name=user.get("display_name", user["username"]),
    )


@app.get(
    "/auth/me",
    response_model=UserInfo,
    tags=["Auth"],
    summary="Get current user info",
)
async def get_me(user: dict = Depends(require_any_role)) -> UserInfo:
    return UserInfo(
        username=user["username"],
        role=user["role"],
        display_name=user.get("display_name", user["username"]),
    )


# ════════════════════════════════════════════════════════════════════════════════
#  SYSTEM
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    return HealthResponse(status="healthy")


# ════════════════════════════════════════════════════════════════════════════════
#  ADMIN ROUTES  (require admin role)
# ════════════════════════════════════════════════════════════════════════════════

@app.post(
    "/upload-documents",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Admin"],
    summary="Upload and ingest a PDF document (admin only)",
)
async def upload_document(
    file: UploadFile = File(...),
    _admin: dict = Depends(require_admin),
) -> UploadResponse:
    filename = file.filename or "unknown.pdf"

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Only PDF files are accepted. Got: '{filename}'.",
        )

    try:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )
        chunks_inserted = ingest_pdf(file_bytes, filename, overwrite=True)
        logger.info("Ingested '%s' → %d chunks.", filename, chunks_inserted)
        return UploadResponse(
            message=f"Successfully ingested '{filename}'.",
            filename=filename,
            chunks_ingested=chunks_inserted,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Ingestion failed for '%s': %s", filename, exc)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}") from exc


@app.get(
    "/list-documents",
    response_model=DocumentListResponse,
    tags=["Admin"],
    summary="List all ingested documents (admin only)",
)
async def list_docs(_admin: dict = Depends(require_admin)) -> DocumentListResponse:
    try:
        docs_raw = list_documents()
        documents = [
            DocumentInfo(
                source=d["_id"],
                chunk_count=d["chunk_count"],
                uploaded_at=d.get("uploaded_at"),
            )
            for d in docs_raw
        ]
        return DocumentListResponse(documents=documents, total=len(documents))
    except Exception as exc:
        logger.exception("Failed to list documents: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve document list: {exc}") from exc


@app.delete(
    "/delete-document/{filename:path}",
    response_model=DeleteResponse,
    tags=["Admin"],
    summary="Delete a document and all its chunks (admin only)",
)
async def delete_doc(
    filename: str,
    _admin: dict = Depends(require_admin),
) -> DeleteResponse:
    if not document_exists(filename):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{filename}' not found.",
        )
    try:
        deleted_count = delete_document(filename)
        logger.info("Deleted %d chunks for '%s'.", deleted_count, filename)
        return DeleteResponse(
            message=f"Deleted '{filename}' and all its chunks.",
            deleted_chunks=deleted_count,
        )
    except Exception as exc:
        logger.exception("Delete failed for '%s': %s", filename, exc)
        raise HTTPException(status_code=500, detail=f"Delete failed: {exc}") from exc


# ════════════════════════════════════════════════════════════════════════════════
#  USER ROUTE  (admin + employee)
# ════════════════════════════════════════════════════════════════════════════════

@app.post(
    "/ask",
    response_model=AskResponse,
    tags=["User"],
    summary="Ask a question (admin + employee)",
)
async def ask_question(
    request: AskRequest,
    user: dict = Depends(require_any_role),
) -> AskResponse:
    question = request.question.strip()
    logger.info("[%s/%s] Question: '%s'", user["username"], user["role"], question)

    try:
        chunks = retrieve_chunks(question)
    except Exception as exc:
        logger.exception("Retrieval failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Vector search failed: {exc}") from exc

    if not chunks:
        log_query(question, [], FALLBACK_ANSWER, [], 0.0)
        return AskResponse(
            answer=FALLBACK_ANSWER,
            citations=[],
            confidence_score=0.0,
            retrieved_chunks=0,
        )

    try:
        result = generate_answer(question, chunks)
    except Exception as exc:
        logger.exception("LLM generation failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Answer generation failed: {exc}") from exc

    log_query(question, chunks, result.answer, result.citations, result.confidence_score)

    return AskResponse(
        answer=result.answer,
        citations=result.citations,
        confidence_score=result.confidence_score,
        retrieved_chunks=result.retrieved_chunks,
    )


# ── Static frontend ───────────────────────────────────────────────────────────
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.isdir(frontend_path):
    # Serve the frontend from the site root (/) instead of under /app
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
