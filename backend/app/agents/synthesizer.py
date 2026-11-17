"""
Agent 2: Synthesizer Agent — Grounded RAG answer generation.

Takes retrieved evidence and uses the LLM service to generate
a factual, grounded answer. Does NOT invent information not in evidence.
"""
from __future__ import annotations

from app.services.llm import generate_answer


async def synthesize(question: str, evidence: list[dict]) -> str:
    """
    Generate a grounded answer from the question and evidence chunks.
    
    Returns the generated answer string.
    """
    if not evidence:
        return (
            "I was unable to find relevant information in the banking policy documents "
            "to answer your question. This has been escalated for admin review."
        )
    return await generate_answer(question, evidence)
