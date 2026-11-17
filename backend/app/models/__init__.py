"""ORM Models package.

Importing all models here ensures they are registered on Base.metadata,
preventing NoReferencedTableError when foreign keys are resolved.
"""
from __future__ import annotations

from app.models.user import User
from app.models.document import Document, DocumentChunk
from app.models.conversation import Conversation, Message, Citation
from app.models.resolution import ResolutionTask, Clarification

__all__ = [
    "User",
    "Document",
    "DocumentChunk",
    "Conversation",
    "Message",
    "Citation",
    "ResolutionTask",
    "Clarification",
]
