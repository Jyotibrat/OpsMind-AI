"""
app/models.py
─────────────
Pydantic v2 request / response models for all API endpoints.
Includes auth models.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    display_name: str


class UserInfo(BaseModel):
    username: str
    role: str
    display_name: str


# ── Q&A ───────────────────────────────────────────────────────────────────────

class AskRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="The employee's question to be answered from corporate documents.",
        examples=["What is the annual leave entitlement policy?"],
    )


class Citation(BaseModel):
    source: str = Field(..., description="Source PDF filename")
    page: int = Field(..., description="Page number within the source document")


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    retrieved_chunks: Optional[int] = None


# ── Documents ──────────────────────────────────────────────────────────────────

class DocumentInfo(BaseModel):
    source: str
    chunk_count: int
    uploaded_at: Optional[datetime] = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentInfo]
    total: int


class DeleteResponse(BaseModel):
    message: str
    deleted_chunks: int


class UploadResponse(BaseModel):
    message: str
    filename: str
    chunks_ingested: int


# ── System ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
    service: str = "OpsMind AI"


class DashboardStats(BaseModel):
    total_documents: int
    total_chunks: int
    recent_queries: int
    service: str = "OpsMind AI"
