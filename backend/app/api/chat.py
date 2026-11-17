"""Chat API — customer chatbot endpoint."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.conversation import Citation, Conversation, Message
from app.models.resolution import ResolutionTask
from app.models.user import User


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

router = APIRouter()


# ─── Schemas ─────────────────────────────────────────────
class ChatRequest(BaseModel):
    question: str
    conversation_id: str | None = None


class CitationOut(BaseModel):
    chunk_id: str
    document_title: str
    excerpt: str
    effective_date: str | None


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    answer: str
    answer_status: str          # 'approved' | 'abstained' | 'error'
    citations: list[CitationOut]
    critic_decision: str | None
    critic_reason: str | None
    resolution_task_id: str | None


class ConversationSummary(BaseModel):
    id: str
    title: str | None
    created_at: datetime
    updated_at: datetime
    message_count: int


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    answer_status: str | None
    created_at: datetime
    citations: list[CitationOut]


class ConversationDetail(BaseModel):
    id: str
    title: str | None
    created_at: datetime
    messages: list[MessageOut]


# ─── Routes ───────────────────────────────────────────────
@router.post("/ask", response_model=ChatResponse)
async def ask(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run the LangGraph multi-agent pipeline and return the verified answer."""
    from app.agents.graph import run_graph

    # Get or create conversation
    conversation: Conversation | None = None
    if body.conversation_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == body.conversation_id,
                Conversation.user_id == current_user.id,
            )
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

    if not conversation:
        conversation = Conversation(
            user_id=current_user.id,
            title=body.question[:80],
        )
        db.add(conversation)
        await db.flush()

    # Save user message
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=body.question,
    )
    db.add(user_msg)
    await db.flush()

    # Run the agent graph
    try:
        result_state = await run_graph(
            question=body.question,
            user_id=current_user.id,
            conversation_id=conversation.id,
        )
    except Exception as exc:
        # Save error message
        err_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content="The AI service encountered an error. Please try again later.",
            answer_status="error",
            agent_trace_json=json.dumps({"error": str(exc)}),
        )
        db.add(err_msg)
        await db.commit()
        return ChatResponse(
            conversation_id=conversation.id,
            message_id=err_msg.id,
            answer=err_msg.content,
            answer_status="error",
            citations=[],
            critic_decision=None,
            critic_reason=str(exc),
            resolution_task_id=None,
        )

    # Save assistant message
    agent_trace = {
        "retrieval_query": result_state.get("retrieval_query"),
        "evidence_count": len(result_state.get("evidence", [])),
        "critic_decision": result_state.get("critic_decision"),
        "critic_reason": result_state.get("critic_reason"),
        "retry_count": result_state.get("retry_count", 0),
        "findings": result_state.get("findings", []),
    }

    answer_status = result_state.get("answer_status", "error")
    final_answer = result_state.get("final_answer", "No answer available.")

    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=final_answer,
        answer_status=answer_status,
        retry_count=result_state.get("retry_count", 0),
        agent_trace_json=json.dumps(agent_trace),
    )
    db.add(assistant_msg)
    await db.flush()

    # Save citations
    citations_out: list[CitationOut] = []
    for cit in result_state.get("citations", []):
        citation = Citation(
            message_id=assistant_msg.id,
            chunk_id=cit.get("chunk_id"),
            document_title=cit.get("document_title", "Unknown"),
            version_label=cit.get("version_label"),
            effective_date=cit.get("effective_date"),
            excerpt=cit.get("excerpt", "")[:500],
            relevance_score=cit.get("combined_score", 0.0),
        )
        db.add(citation)
        citations_out.append(CitationOut(
            chunk_id=cit.get("chunk_id", ""),
            document_title=cit.get("document_title", ""),
            excerpt=cit.get("excerpt", "")[:300],
            effective_date=cit.get("effective_date"),
        ))

    # If abstained, create resolution task
    resolution_task_id: str | None = None
    if answer_status == "abstained":
        task = ResolutionTask(
            question=body.question,
            conversation_id=conversation.id,
            message_id=assistant_msg.id,
            abstention_reason=result_state.get("critic_reason", "Unable to verify answer"),
            retrieved_evidence_json=json.dumps([
                {"chunk_id": e["chunk_id"], "document_title": e["document_title"],
                 "excerpt": e["content"][:200]}
                for e in result_state.get("evidence", [])
            ]),
            status="open",
        )
        db.add(task)
        await db.flush()
        resolution_task_id = task.id

    # Update conversation updated_at and title
    conversation.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return ChatResponse(
        conversation_id=conversation.id,
        message_id=assistant_msg.id,
        answer=final_answer,
        answer_status=answer_status,
        citations=citations_out,
        critic_decision=result_state.get("critic_decision"),
        critic_reason=result_state.get("critic_reason"),
        resolution_task_id=resolution_task_id,
    )


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    )
    conversations = result.scalars().all()
    out = []
    for conv in conversations:
        msg_result = await db.execute(
            select(Message).where(Message.conversation_id == conv.id)
        )
        msgs = msg_result.scalars().all()
        out.append(ConversationSummary(
            id=conv.id,
            title=conv.title,
            created_at=_ensure_utc(conv.created_at),
            updated_at=_ensure_utc(conv.updated_at),
            message_count=len(msgs),
        ))
    return out


@router.get("/conversations/{conv_id}", response_model=ConversationDetail)
async def get_conversation(
    conv_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at)
    )
    messages = msg_result.scalars().all()

    messages_out = []
    for msg in messages:
        cit_result = await db.execute(
            select(Citation).where(Citation.message_id == msg.id)
        )
        cits = cit_result.scalars().all()
        messages_out.append(MessageOut(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            answer_status=msg.answer_status,
            created_at=_ensure_utc(msg.created_at),
            citations=[
                CitationOut(
                    chunk_id=c.chunk_id or "",
                    document_title=c.document_title,
                    excerpt=c.excerpt,
                    effective_date=c.effective_date,
                )
                for c in cits
            ],
        ))

    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        messages=messages_out,
    )
