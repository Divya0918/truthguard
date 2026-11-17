"""Resolution models — unanswered questions and admin clarifications.

Workflow:
  1. Critic Agent returns ABSTAIN  →  ResolutionTask created (status='open')
  2. Admin opens task, types an answer  →  Clarification created (status='draft')
  3. Admin explicitly approves it  →  Clarification status='approved'
  4. Admin publishes it  →  Clarification status='published'; chunks indexed
  5. Future customer questions now match the published clarification chunks.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ResolutionTask(Base):
    """An unanswered question that requires admin attention."""
    __tablename__ = "resolution_tasks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # The original question
    question: Mapped[str] = mapped_column(Text, nullable=False)

    # Trace back to the conversation
    conversation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    message_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )

    # Why did the agent abstain?
    abstention_reason: Mapped[str] = mapped_column(Text, nullable=False)

    # JSON string: list of retrieved evidence summaries at abstention time
    retrieved_evidence_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        SAEnum("open", "in_review", "resolved", name="task_status"),
        nullable=False,
        default="open",
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    # Relationships
    clarification: Mapped["Clarification | None"] = relationship(
        "Clarification", back_populates="task", uselist=False
    )

    def __repr__(self) -> str:
        return f"<ResolutionTask id={self.id} status={self.status}>"


class Clarification(Base):
    """An admin-authored authoritative answer to a resolution task.

    Only 'published' clarifications are indexed and made available
    to the retrieval agents. Draft and approved clarifications are
    never exposed to customers.
    """
    __tablename__ = "clarifications"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("resolution_tasks.id", ondelete="CASCADE"),
        nullable=False, unique=True
    )

    # The question this addresses (copied from task for display)
    question: Mapped[str] = mapped_column(Text, nullable=False)

    # The authoritative answer typed by the admin
    answer: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(
        SAEnum("draft", "approved", "published", name="clarification_status"),
        nullable=False,
        default="draft",
        index=True,
    )

    created_by_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    approved_by_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Chunk ID created when published (so it can be cited in future answers)
    chunk_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    task: Mapped["ResolutionTask"] = relationship("ResolutionTask", back_populates="clarification")

    def __repr__(self) -> str:
        return f"<Clarification id={self.id} status={self.status}>"
