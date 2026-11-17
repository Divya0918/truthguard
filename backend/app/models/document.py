"""Document models — uploaded files, versioned, with extracted text chunks."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text,
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
import app.models.user  # ensure User is registered in metadata for ForeignKey("users.id")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    """A policy document uploaded by an admin.

    Approval workflow:
      pending → processing → published  (normal path)
      pending → rejected               (rejected by admin)

    Only 'published' documents are visible to the retrieval agents.
    """
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # File info
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_type: Mapped[str] = mapped_column(
        SAEnum("pdf", "docx", "txt", "md", name="file_type_enum"), nullable=False
    )
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Approval state
    status: Mapped[str] = mapped_column(
        SAEnum("pending", "processing", "published", "rejected", name="doc_status"),
        nullable=False,
        default="pending",
        index=True,
    )

    # Provenance
    version_label: Mapped[str | None] = mapped_column(String(50), nullable=True)   # e.g. "v2.1"
    effective_date: Mapped[str | None] = mapped_column(String(50), nullable=True)   # e.g. "2024-01-01"
    supersedes_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("documents.id"), nullable=True
    )

    # Who uploaded (nullable for system-ingested policy documents)
    uploaded_by_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    # Processing metadata
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )

    @property
    def is_priority(self) -> bool:
        return (
            self.version_label == "PRIORITY"
            or "priority_document" in (self.original_filename or "").lower()
            or "priority document" in (self.title or "").lower()
        )

    def __repr__(self) -> str:
        return f"<Document id={self.id} title={self.title!r} status={self.status}>"


class DocumentChunk(Base):
    """A text passage extracted from a document.

    embeddings_json stores a JSON array (list of floats).
    At query time, cosine similarity is computed in Python for SQLite,
    or via pgvector ANN when PGVECTOR_ENABLED=true with PostgreSQL.
    """
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Content
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Embedding stored as JSON text: "[0.123, -0.456, ...]"
    embedding_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metadata for citations
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    document_title: Mapped[str] = mapped_column(String(500), nullable=False)
    effective_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    version_label: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Full-text search: pre-built tsv stored as text for SQLite compat
    # On PostgreSQL, we query using to_tsvector() at query time
    content_tsv: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<Chunk id={self.id} doc={self.document_id} idx={self.chunk_index}>"
