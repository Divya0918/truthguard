"""Admin Documents API — upload, list, details, approve, retry ingestion."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_admin
from app.core.database import get_db
from app.models.document import Document, DocumentChunk
from app.models.user import User

router = APIRouter()

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_TYPES = {"pdf", "docx", "txt", "md"}


# ─── Schemas ─────────────────────────────────────────────
class DocumentOut(BaseModel):
    id: str
    title: str
    description: str | None
    original_filename: str
    file_type: str
    status: str
    version_label: str | None
    effective_date: str | None
    chunk_count: int
    processing_error: str | None
    created_at: datetime
    published_at: datetime | None
    supersedes_id: str | None
    is_priority: bool = False


class ChunkDetail(BaseModel):
    chunk_index: int
    content: str
    section_title: str | None
    word_count: int


class DocumentDetail(DocumentOut):
    file_size_bytes: int | None
    content: str | None = None
    chunks: list[ChunkDetail] = []
    chunks_preview: list[dict] = []


class PriorityEntryRequest(BaseModel):
    question: str
    answer: str
    timestamp: str | None = None


# ─── Routes ───────────────────────────────────────────────
@router.post("/upload", response_model=DocumentOut, status_code=201)
async def upload_document(
    title: str = Form(...),
    description: str = Form(""),
    version_label: str = Form(""),
    effective_date: str = Form(""),
    supersedes_id: str = Form(""),
    file: UploadFile = File(...),
    current_admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    # Validate file type
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_TYPES:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Allowed: {ALLOWED_TYPES}")

    # Read and validate size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, "File too large (max 20 MB)")
    if len(content) == 0:
        raise HTTPException(400, "Uploaded file is empty")

    # Save with safe UUID filename
    safe_name = f"{uuid.uuid4().hex}.{ext}"
    dest = (UPLOAD_DIR / safe_name).resolve()
    dest.write_bytes(content)

    # Create DB record
    doc = Document(
        title=title,
        description=description or None,
        original_filename=file.filename or safe_name,
        file_path=str(dest),
        file_type=ext,
        file_size_bytes=len(content),
        status="pending",
        version_label=version_label or None,
        effective_date=effective_date or None,
        supersedes_id=supersedes_id or None,
        uploaded_by_id=current_admin.id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Start ingestion in background
    import asyncio
    asyncio.create_task(_run_ingestion(doc.id))

    return _doc_to_out(doc)


async def _run_ingestion(doc_id: str) -> None:
    """Background ingestion task."""
    try:
        from app.services.ingestion import ingest_document
        await ingest_document(doc_id)
    except Exception as exc:
        print(f"[ERROR] Background ingestion failed for {doc_id}: {exc}")


@router.get("/", response_model=list[DocumentOut])
async def list_documents(
    status: str | None = None,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(Document).order_by(Document.created_at.desc())
    if status:
        q = q.where(Document.status == status)
    result = await db.execute(q)
    docs = result.scalars().all()
    return [_doc_to_out(d) for d in docs]


@router.get("/priority/details", response_model=DocumentDetail)
async def get_priority_document_details(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full details of the Priority Document."""
    from app.services.priority_doc import get_or_create_priority_document
    doc = await get_or_create_priority_document()
    return await get_document(doc.id, admin, db)


@router.post("/priority/entry", response_model=DocumentOut)
async def add_priority_entry(
    body: PriorityEntryRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Add a question and answer with timestamp directly into the Priority Document."""
    from app.services.priority_doc import append_to_priority_doc
    priority_doc = await append_to_priority_doc(
        question=body.question,
        answer=body.answer,
        timestamp_str=body.timestamp,
    )
    return _doc_to_out(priority_doc)


@router.get("/{doc_id}", response_model=DocumentDetail)
async def get_document(
    doc_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    doc = await _fetch_doc(doc_id, db)
    chunks_result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == doc_id)
        .order_by(DocumentChunk.chunk_index)
    )
    chunks = chunks_result.scalars().all()

    # Extract full text content
    content_str = None
    if doc.file_path:
        try:
            from app.services.ingestion import extract_text
            content_str = extract_text(doc.file_path, doc.file_type)
        except Exception:
            if os.path.exists(doc.file_path):
                try:
                    content_str = Path(doc.file_path).read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass
    if not content_str and chunks:
        content_str = "\n\n".join(c.content for c in chunks)

    chunk_details = [
        ChunkDetail(
            chunk_index=c.chunk_index,
            content=c.content,
            section_title=c.section_title,
            word_count=c.word_count,
        )
        for c in chunks
    ]
    preview = [
        {"index": c.chunk_index, "excerpt": c.content[:200], "section": c.section_title}
        for c in chunks[:5]
    ]

    base_out = _doc_to_out(doc).model_dump()
    return DocumentDetail(
        **base_out,
        file_size_bytes=doc.file_size_bytes,
        content=content_str,
        chunks=chunk_details,
        chunks_preview=preview,
    )


@router.post("/{doc_id}/publish", response_model=DocumentOut)
async def publish_document(
    doc_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    doc = await _fetch_doc(doc_id, db)
    if doc.status == "processing":
        raise HTTPException(409, "Document is still being processed")
    if doc.status == "rejected":
        raise HTTPException(409, "Fix processing errors before publishing")

    # If document hasn't been chunked yet, run ingestion to extract and embed chunks
    if doc.chunk_count == 0 and not doc.file_path.startswith("clarification:"):
        from app.services.ingestion import ingest_document
        await ingest_document(doc.id)
        await db.refresh(doc)
    else:
        doc.status = "published"
        doc.published_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(doc)
    return _doc_to_out(doc)


@router.post("/{doc_id}/reject", response_model=DocumentOut)
async def reject_document(
    doc_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    doc = await _fetch_doc(doc_id, db)
    doc.status = "rejected"
    await db.commit()
    await db.refresh(doc)
    return _doc_to_out(doc)


@router.post("/{doc_id}/retry", response_model=DocumentOut)
async def retry_ingestion(
    doc_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    doc = await _fetch_doc(doc_id, db)
    if doc.status not in ("rejected", "pending"):
        raise HTTPException(409, "Only pending or rejected documents can be retried")

    import asyncio
    asyncio.create_task(_run_ingestion(doc_id))
    doc.status = "pending"
    doc.processing_error = None
    await db.commit()
    await db.refresh(doc)
    return _doc_to_out(doc)


# ─── Helpers ──────────────────────────────────────────────
async def _fetch_doc(doc_id: str, db: AsyncSession) -> Document:
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


from datetime import datetime, timezone


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _doc_to_out(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        title=doc.title,
        description=doc.description,
        original_filename=doc.original_filename,
        file_type=doc.file_type,
        status=doc.status,
        version_label=doc.version_label,
        effective_date=doc.effective_date,
        chunk_count=doc.chunk_count,
        processing_error=doc.processing_error,
        created_at=_ensure_utc(doc.created_at),
        published_at=_ensure_utc(doc.published_at),
        supersedes_id=doc.supersedes_id,
        is_priority=bool(getattr(doc, "is_priority", False)),
    )
