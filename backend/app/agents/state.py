"""Shared TypedDict state for the LangGraph workflow.
Every node reads from and writes to this state.
"""
from __future__ import annotations

import operator
from typing import Annotated
from typing_extensions import TypedDict


class EvidenceChunk(TypedDict):
    chunk_id: str
    document_id: str
    document_title: str
    version_label: str | None
    effective_date: str | None
    content: str
    keyword_score: float
    semantic_score: float
    combined_score: float


class CitationRef(TypedDict):
    chunk_id: str
    document_title: str
    excerpt: str
    effective_date: str | None


class VerificationFinding(TypedDict):
    claim: str
    supported: bool
    reason: str
    chunk_id: str | None


class AgentState(TypedDict):
    # Input
    question: str
    conversation_id: str | None
    user_id: str

    # Retriever output
    evidence: Annotated[list[EvidenceChunk], operator.add]
    retrieval_query: str

    # Synthesizer output
    draft_answer: str
    citations: Annotated[list[CitationRef], operator.add]

    # Critic output
    critic_decision: str   # 'APPROVED' | 'RETRY' | 'ABSTAIN'
    critic_reason: str
    findings: Annotated[list[VerificationFinding], operator.add]

    # Control
    retry_count: int
    max_retries: int
    error: str | None

    # Final
    final_answer: str | None
    answer_status: str | None  # 'approved' | 'abstained' | 'error'
