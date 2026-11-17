"""Admin Chat History API — view all customer conversations and message details."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

from app.api.auth import require_admin
from app.core.database import get_db
from app.models.conversation import Citation, Conversation, Message
from app.models.user import User

router = APIRouter()


# ─── Schemas ─────────────────────────────────────────────
class CitationOut(BaseModel):
    chunk_id: str
    document_title: str
    excerpt: str
    effective_date: str | None
    relevance_score: float


class MessageAdminOut(BaseModel):
    id: str
    role: str
    content: str
    answer_status: str | None
    retry_count: int
    created_at: datetime
    citations: list[CitationOut]
    agent_trace: dict | None


class ConvAdminSummary(BaseModel):
    id: str
    title: str | None
    user_id: str
    user_email: str | None
    created_at: datetime
    updated_at: datetime
    message_count: int
    has_abstention: bool


class ConvAdminDetail(BaseModel):
    id: str
    title: str | None
    user_id: str
    created_at: datetime
    messages: list[MessageAdminOut]


# ─── Routes ───────────────────────────────────────────────
@router.get("/conversations", response_model=list[ConvAdminSummary])
async def admin_list_conversations(
    skip: int = 0,
    limit: int = 50,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation)
        .order_by(Conversation.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    conversations = result.scalars().all()

    out = []
    for conv in conversations:
        # Get message count and check for abstentions
        msgs_result = await db.execute(
            select(Message).where(Message.conversation_id == conv.id)
        )
        msgs = msgs_result.scalars().all()
        has_abstention = any(m.answer_status == "abstained" for m in msgs)

        # Get user email
        from app.models.user import User as UserModel
        user_result = await db.execute(
            select(UserModel).where(UserModel.id == conv.user_id)
        )
        user = user_result.scalar_one_or_none()

        out.append(ConvAdminSummary(
            id=conv.id,
            title=conv.title,
            user_id=conv.user_id,
            user_email=user.email if user else None,
            created_at=_ensure_utc(conv.created_at),
            updated_at=_ensure_utc(conv.updated_at),
            message_count=len(msgs),
            has_abstention=has_abstention,
        ))
    return out


@router.get("/conversations/{conv_id}", response_model=ConvAdminDetail)
async def admin_get_conversation(
    conv_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(Conversation.id == conv_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversation not found")

    msgs_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at)
    )
    messages = msgs_result.scalars().all()

    messages_out = []
    for msg in messages:
        cits_result = await db.execute(
            select(Citation).where(Citation.message_id == msg.id)
        )
        cits = cits_result.scalars().all()

        # Parse agent trace
        trace = None
        if msg.agent_trace_json:
            try:
                trace = json.loads(msg.agent_trace_json)
            except Exception:
                trace = {"raw": msg.agent_trace_json}

        messages_out.append(MessageAdminOut(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            answer_status=msg.answer_status,
            retry_count=msg.retry_count,
            created_at=_ensure_utc(msg.created_at),
            citations=[
                CitationOut(
                    chunk_id=c.chunk_id or "",
                    document_title=c.document_title,
                    excerpt=c.excerpt,
                    effective_date=c.effective_date,
                    relevance_score=c.relevance_score,
                )
                for c in cits
            ],
            agent_trace=trace,
        ))

    return ConvAdminDetail(
        id=conv.id,
        title=conv.title,
        user_id=conv.user_id,
        created_at=conv.created_at,
        messages=messages_out,
    )


@router.get("/stats")
async def admin_stats(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Dashboard statistics."""
    from app.models.document import Document
    from app.models.resolution import ResolutionTask

    total_convs = (await db.execute(select(func.count(Conversation.id)))).scalar()
    total_msgs = (await db.execute(select(func.count(Message.id)))).scalar()
    approved_msgs = (await db.execute(
        select(func.count(Message.id)).where(Message.answer_status == "approved")
    )).scalar()
    abstained_msgs = (await db.execute(
        select(func.count(Message.id)).where(Message.answer_status == "abstained")
    )).scalar()
    total_docs = (await db.execute(select(func.count(Document.id)))).scalar()
    published_docs = (await db.execute(
        select(func.count(Document.id)).where(Document.status == "published")
    )).scalar()
    open_tasks = (await db.execute(
        select(func.count(ResolutionTask.id)).where(ResolutionTask.status == "open")
    )).scalar()

    return {
        "total_conversations": total_convs,
        "total_messages": total_msgs,
        "approved_answers": approved_msgs,
        "abstained_answers": abstained_msgs,
        "total_documents": total_docs,
        "published_documents": published_docs,
        "open_resolution_tasks": open_tasks,
    }
