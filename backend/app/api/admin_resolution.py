"""Admin Resolution API — unanswered questions and clarification workflow."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_admin
from app.core.database import get_db
from app.models.resolution import Clarification, ResolutionTask
from app.models.user import User

router = APIRouter()


# ─── Schemas ─────────────────────────────────────────────
class EvidenceItem(BaseModel):
    chunk_id: str | None
    document_title: str
    excerpt: str


class TaskOut(BaseModel):
    id: str
    question: str
    abstention_reason: str
    status: str
    created_at: datetime
    updated_at: datetime
    conversation_id: str | None
    retrieved_evidence: list[EvidenceItem]
    clarification_id: str | None
    clarification_status: str | None


class ClarificationOut(BaseModel):
    id: str
    task_id: str
    question: str
    answer: str
    status: str
    created_at: datetime
    approved_at: datetime | None
    published_at: datetime | None


class CreateClarificationRequest(BaseModel):
    answer: str


class UpdateClarificationRequest(BaseModel):
    answer: str | None = None


class ResolvePriorityRequest(BaseModel):
    answer: str
    timestamp: str | None = None


# ─── Routes ───────────────────────────────────────────────
@router.get("/tasks", response_model=list[TaskOut])
async def list_tasks(
    status: str | None = None,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(ResolutionTask).order_by(ResolutionTask.created_at.desc())
    if status:
        q = q.where(ResolutionTask.status == status)
    result = await db.execute(q)
    tasks = result.scalars().all()
    return [await _task_to_out(t, db) for t in tasks]


@router.get("/tasks/{task_id}", response_model=TaskOut)
async def get_task(
    task_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    task = await _fetch_task(task_id, db)
    return await _task_to_out(task, db)


@router.post("/tasks/{task_id}/clarify", response_model=ClarificationOut, status_code=201)
async def create_clarification(
    task_id: str,
    body: CreateClarificationRequest,
    current_admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin types an answer — saved as draft."""
    task = await _fetch_task(task_id, db)
    if task.status == "resolved":
        raise HTTPException(409, "Task already resolved")

    # Check if clarification already exists
    existing = await db.execute(
        select(Clarification).where(Clarification.task_id == task_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Clarification already exists for this task")

    clarification = Clarification(
        task_id=task_id,
        question=task.question,
        answer=body.answer,
        status="draft",
        created_by_id=current_admin.id,
    )
    db.add(clarification)
    task.status = "in_review"
    await db.commit()
    await db.refresh(clarification)
    return _clar_to_out(clarification)


@router.put("/tasks/{task_id}/clarify/{clar_id}", response_model=ClarificationOut)
async def update_clarification(
    task_id: str,
    clar_id: str,
    body: UpdateClarificationRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    clar = await _fetch_clarification(clar_id, db)
    if clar.task_id != task_id:
        raise HTTPException(404, "Clarification not found for this task")
    if clar.status == "published":
        raise HTTPException(409, "Cannot edit a published clarification")
    if body.answer:
        clar.answer = body.answer
    await db.commit()
    await db.refresh(clar)
    return _clar_to_out(clar)


@router.post("/tasks/{task_id}/clarify/{clar_id}/approve", response_model=ClarificationOut)
async def approve_clarification(
    task_id: str,
    clar_id: str,
    current_admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    clar = await _fetch_clarification(clar_id, db)
    if clar.status not in ("draft",):
        raise HTTPException(409, f"Cannot approve from status '{clar.status}'")
    clar.status = "approved"
    clar.approved_by_id = current_admin.id
    clar.approved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(clar)
    return _clar_to_out(clar)


@router.post("/tasks/{task_id}/clarify/{clar_id}/publish", response_model=ClarificationOut)
async def publish_clarification(
    task_id: str,
    clar_id: str,
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Publish: index the clarification as a document chunk for future retrieval."""
    clar = await _fetch_clarification(clar_id, db)
    if clar.status != "approved":
        raise HTTPException(409, "Clarification must be approved before publishing")

    clar.status = "published"
    clar.published_at = datetime.now(timezone.utc)

    task = await _fetch_task(task_id, db)
    task.status = "resolved"
    task.resolved_at = datetime.now(timezone.utc)
    task.resolved_by_id = current_admin.id

    await db.commit()
    await db.refresh(clar)

    # Index in background
    background_tasks.add_task(_index_clarification, clar.id)

    return _clar_to_out(clar)


@router.post("/tasks/{task_id}/resolve-priority", response_model=TaskOut)
async def resolve_task_with_priority(
    task_id: str,
    body: ResolvePriorityRequest,
    current_admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Resolve an unanswered question by adding it directly to the Priority Document."""
    task = await _fetch_task(task_id, db)
    if not body.answer.strip():
        raise HTTPException(400, "Answer cannot be empty")

    from app.services.priority_doc import append_to_priority_doc
    await append_to_priority_doc(
        question=task.question,
        answer=body.answer,
        timestamp_str=body.timestamp,
    )

    task.status = "resolved"
    task.resolved_at = datetime.now(timezone.utc)
    task.resolved_by_id = current_admin.id
    await db.commit()
    await db.refresh(task)

    return await _task_to_out(task, db)


@router.post("/tasks/{task_id}/upload-policy", response_model=dict, status_code=201)
async def upload_resolution_policy(
    task_id: str,
    title: str = Form(...),
    effective_date: str = Form(""),
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Upload a policy document to resolve an unanswered question."""
    from app.api.admin_docs import upload_document
    # Delegate to regular upload — document will be ingested and published
    doc_out = await upload_document(
        title=title,
        description=f"Uploaded to resolve task {task_id}",
        version_label="",
        effective_date=effective_date,
        supersedes_id="",
        file=file,
        current_admin=current_admin,
        db=db,
    )

    task = await _fetch_task(task_id, db)
    task.status = "resolved"
    task.resolved_at = datetime.now(timezone.utc)
    task.resolved_by_id = current_admin.id
    await db.commit()

    return {"document_id": doc_out.id, "task_id": task_id, "status": "resolved"}


@router.get("/tasks/{task_id}/clarification", response_model=ClarificationOut | None)
async def get_task_clarification(
    task_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _fetch_task(task_id, db)
    result = await db.execute(
        select(Clarification).where(Clarification.task_id == task_id)
    )
    clar = result.scalar_one_or_none()
    return _clar_to_out(clar) if clar else None


# ─── Helpers ──────────────────────────────────────────────
async def _index_clarification(clar_id: str) -> None:
    """Index a published clarification as a document chunk."""
    from app.core.database import AsyncSessionLocal
    from app.models.document import Document, DocumentChunk
    from app.services.embedding import embedding_service

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Clarification).where(Clarification.id == clar_id)
        )
        clar = result.scalar_one_or_none()
        if not clar:
            return

        # Create a synthetic Document record for the clarification
        synth_doc = Document(
            title=f"Admin Clarification: {clar.question[:80]}",
            description="Published admin clarification",
            original_filename=f"clarification_{clar.id}.txt",
            file_path=f"clarification:{clar.id}",
            file_type="txt",
            status="published",
            version_label="admin-v1",
            effective_date=str(clar.published_at.date()) if clar.published_at else None,
            uploaded_by_id=clar.created_by_id,
            published_at=clar.published_at,
            chunk_count=1,
        )
        db.add(synth_doc)
        await db.flush()

        text = f"Q: {clar.question}\nA: {clar.answer}"
        embeddings = await embedding_service.encode([text])
        chunk = DocumentChunk(
            document_id=synth_doc.id,
            chunk_index=0,
            content=text,
            word_count=len(text.split()),
            embedding_json=json.dumps(embeddings[0]),
            document_title=synth_doc.title,
            effective_date=synth_doc.effective_date,
            version_label="admin-v1",
        )
        db.add(chunk)
        await db.flush()

        # Link chunk to clarification
        clar.chunk_id = chunk.id
        await db.commit()


async def _fetch_task(task_id: str, db: AsyncSession) -> ResolutionTask:
    result = await db.execute(
        select(ResolutionTask).where(ResolutionTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")
    return task


async def _fetch_clarification(clar_id: str, db: AsyncSession) -> Clarification:
    result = await db.execute(
        select(Clarification).where(Clarification.id == clar_id)
    )
    clar = result.scalar_one_or_none()
    if not clar:
        raise HTTPException(404, "Clarification not found")
    return clar


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def _task_to_out(task: ResolutionTask, db: AsyncSession) -> TaskOut:
    evidence: list[EvidenceItem] = []
    if task.retrieved_evidence_json:
        try:
            raw = json.loads(task.retrieved_evidence_json)
            for item in raw:
                evidence.append(EvidenceItem(
                    chunk_id=item.get("chunk_id"),
                    document_title=item.get("document_title", ""),
                    excerpt=item.get("excerpt", ""),
                ))
        except Exception:
            pass

    clar_result = await db.execute(
        select(Clarification).where(Clarification.task_id == task.id)
    )
    clar = clar_result.scalar_one_or_none()

    return TaskOut(
        id=task.id,
        question=task.question,
        abstention_reason=task.abstention_reason,
        status=task.status,
        created_at=_ensure_utc(task.created_at),
        updated_at=_ensure_utc(task.updated_at),
        conversation_id=task.conversation_id,
        retrieved_evidence=evidence,
        clarification_id=clar.id if clar else None,
        clarification_status=clar.status if clar else None,
    )


def _clar_to_out(clar: Clarification) -> ClarificationOut:
    return ClarificationOut(
        id=clar.id,
        task_id=clar.task_id,
        question=clar.question,
        answer=clar.answer,
        status=clar.status,
        created_at=_ensure_utc(clar.created_at),
        approved_at=_ensure_utc(clar.approved_at),
        published_at=_ensure_utc(clar.published_at),
    )
