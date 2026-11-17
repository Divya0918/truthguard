"""Conversation and Message models — customer chat sessions."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime, Float, ForeignKey, Integer, String, Text,
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Conversation(Base):
    """A customer's chat session. One conversation = one thread of messages."""
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)  # auto set from first Q
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    # Relationships
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan",
        order_by="Message.created_at"
    )

    def __repr__(self) -> str:
        return f"<Conversation id={self.id} user={self.user_id}>"


class Message(Base):
    """A single turn in a conversation.

    role='user'      → the customer's question
    role='assistant' → the AI's verified answer (or abstention)

    answer_status:
      'approved'  → Critic accepted the answer
      'abstained' → Critic could not verify; resolution task created
      'error'     → processing failure
      null        → user message (not applicable)

    agent_trace_json stores the full agent execution log for admin inspection.
    """
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(
        SAEnum("user", "assistant", name="message_role"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Only set on assistant messages
    answer_status: Mapped[str | None] = mapped_column(
        SAEnum("approved", "abstained", "error", name="answer_status_enum"), nullable=True
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # JSON string — full trace of all 3 agents for admin review
    agent_trace_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
    citations: Mapped[list["Citation"]] = relationship(
        "Citation", back_populates="message", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Message id={self.id} role={self.role} status={self.answer_status}>"


class Citation(Base):
    """A document chunk that was cited as evidence in an assistant message."""
    __tablename__ = "citations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True
    )

    # Denormalized for display (so citation still shows even if chunk deleted)
    document_title: Mapped[str] = mapped_column(String(500), nullable=False)
    version_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    effective_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Relationships
    message: Mapped["Message"] = relationship("Message", back_populates="citations")

    def __repr__(self) -> str:
        return f"<Citation id={self.id} doc={self.document_title!r}>"
