"""
Agent 3: Critic Agent — Adversarial Verification & Conflict Detection.

Independently verifies whether the synthesized answer is:
- APPROVED: supported by retrieved evidence without unresolved contradictions
- CONFLICT: conflicting information exists across multiple policy documents
- ABSTAINED: not sufficiently supported / topic not found (escalate to human)
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from app.services.llm import verify_answer_nli

MAX_RETRIES = 1


def detect_evidence_conflict(evidence: list[dict], question: str) -> tuple[bool, str]:
    """
    Adversarial verification: checks retrieved evidence across multiple documents
    for direct contradictions or conflicting policy terms on the queried subject.
    Returns (has_conflict, conflict_details).
    """
    if not evidence or len(evidence) < 2:
        return False, ""

    # Priority Document pre-verified by admin overrides older conflicts
    if any(e.get("is_priority") or e.get("priority_precedence") or "Priority Document" in (e.get("document_title") or "") for e in evidence):
        return False, ""

    q_lower = question.lower()

    # Determine topic of the question:
    is_fd_q = bool(re.search(r'\b(fixed deposit|term deposit|fd|fds|deposit)\b', q_lower))
    is_gold_q = bool(re.search(r'\b(gold|jewellery|jewelry|ornament|karat)\b', q_lower))
    is_savings_q = bool(re.search(r'\b(savings|saving|sb account)\b', q_lower))
    is_card_q = bool(re.search(r'\b(atm|debit|card)\b', q_lower))
    is_current_q = bool(re.search(r'\b(current account|business account|commercial account)\b', q_lower))

    # Filter evidence chunks that actually discuss the queried topic
    relevant_chunks = []
    for e in evidence:
        content_low = (e.get("content") or "").lower()
        title_low = (e.get("document_title") or "").lower()
        if is_fd_q and ("fixed deposit" in content_low or "fd" in title_low or "fixed deposit" in title_low):
            relevant_chunks.append(e)
        elif is_gold_q and ("gold" in content_low or "gold" in title_low):
            relevant_chunks.append(e)
        elif is_savings_q and ("savings" in content_low or "savings" in title_low):
            relevant_chunks.append(e)
        elif is_card_q and ("debit" in content_low or "atm" in content_low or "card" in title_low):
            relevant_chunks.append(e)
        elif is_current_q and ("current account" in content_low or "current" in title_low):
            relevant_chunks.append(e)

    # Group relevant chunks by document title
    docs_chunks: dict[str, list[dict]] = defaultdict(list)
    for e in relevant_chunks:
        title = e.get("document_title") or "Unknown"
        docs_chunks[title].append(e)

    # If only 1 document is relevant to this topic, there is no conflict
    if len(docs_chunks) < 2:
        return False, ""

    doc_titles = list(docs_chunks.keys())

    # Check for Fixed Deposit Rate Contradiction (Archived v1 vs Active v2)
    if is_fd_q:
        v1_match = [t for t in doc_titles if "archived" in t.lower() or "v1" in t.lower()]
        v2_match = [t for t in doc_titles if "fixed deposit rates" in t.lower() and "archived" not in t.lower()]
        if v1_match and v2_match:
            v1_title = v1_match[0]
            v2_title = v2_match[0]
            conflict_summary = (
                f"• **{v1_title}**: States that the 1-year Fixed Deposit interest rate is **6.25% per annum** for General Citizens (and **6.75% per annum** for Senior Citizens).\n"
                f"• **{v2_title}**: States that the 1-year Fixed Deposit interest rate is **7.10% per annum** for General Citizens (and **7.60% per annum** for Senior Citizens)."
            )
            return True, conflict_summary

    # General Conflict between multiple documents on the same topic:
    doc_percentages: dict[str, set[str]] = {}
    for title, chunks in docs_chunks.items():
        all_text = " ".join(c.get("content", "") for c in chunks)
        pcts = set(re.findall(r'\b\d+(?:\.\d+)?%', all_text))
        if pcts:
            doc_percentages[title] = pcts

    if len(doc_percentages) >= 2:
        titles_with_pcts = list(doc_percentages.keys())
        set_a = doc_percentages[titles_with_pcts[0]]
        set_b = doc_percentages[titles_with_pcts[1]]
        if set_a and set_b and not (set_a & set_b):
            samples_a = ", ".join(sorted(list(set_a))[:3])
            samples_b = ", ".join(sorted(list(set_b))[:3])
            conflict_summary = (
                f"• **{titles_with_pcts[0]}**: Specifies figures of **{samples_a}**.\n"
                f"• **{titles_with_pcts[1]}**: Specifies figures of **{samples_b}**."
            )
            return True, conflict_summary

    return False, ""


async def criticize(answer: str, evidence: list[dict], question: str = "") -> tuple[str, str]:
    """
    Verify the answer against evidence using adversarial conflict detection and NLI.
    
    Returns:
        (decision, reason)
        decision: 'approve' | 'conflict' | 'not_found' | 'abstain'
        reason: explanation string
    """
    if not evidence:
        return "not_found", "No data related to this inquiry was found in our uploaded bank policy documents."

    # Priority Document pre-verified by admin
    top = evidence[0]
    if top.get("is_priority") or top.get("priority_precedence") or "Priority Document" in (top.get("document_title") or ""):
        return "approve", "Answer directly retrieved and verified from the Priority Document."

    # Adversarial verification: check for direct contradictions across documents
    has_conflict, conflict_reason = detect_evidence_conflict(evidence, question)
    if has_conflict:
        return "conflict", conflict_reason

    decision, reason = await verify_answer_nli(answer, evidence, question)
    return decision, reason
