"""
LangGraph orchestration graph — TruthGuard multi-agent pipeline.

State machine:
  retrieve → synthesize → criticize → [approve | retry → synthesize | abstain]

Each node is a genuine async function that calls an independent agent.
The graph uses conditional edges to decide whether to retry synthesis
or accept the answer.
"""
from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph  # type: ignore

from app.agents.critic import criticize
from app.agents.retriever import retrieve
from app.agents.synthesizer import synthesize

MAX_RETRIES = 2


# ─── State ────────────────────────────────────────────────
class AgentState(TypedDict, total=False):
    question: str
    user_id: str
    conversation_id: str

    # Retriever output
    evidence: list[dict]
    retrieval_query: str

    # Synthesizer output
    generated_answer: str
    retry_count: int

    # Critic output
    critic_decision: str   # 'approve' | 'abstain'
    critic_reason: str
    findings: list[str]

    # Final output
    final_answer: str
    answer_status: str     # 'approved' | 'abstained' | 'error'
    citations: list[dict]


# ─── Nodes ────────────────────────────────────────────────
async def retriever_node(state: AgentState) -> AgentState:
    """Agent 1: Hybrid BM25 + Semantic retrieval."""
    question = state["question"]
    evidence = await retrieve(question, top_k=5)
    return {
        **state,
        "evidence": evidence,
        "retrieval_query": question,
    }


async def synthesizer_node(state: AgentState) -> AgentState:
    """Agent 2: Grounded RAG answer generation."""
    question = state["question"]
    evidence = state.get("evidence", [])
    answer = await synthesize(question, evidence)
    return {
        **state,
        "generated_answer": answer,
        "retry_count": state.get("retry_count", 0),
    }


async def critic_node(state: AgentState) -> AgentState:
    """Agent 3: NLI verification of the synthesized answer."""
    answer = state.get("generated_answer", "")
    evidence = state.get("evidence", [])
    question = state.get("question", "")
    decision, reason = await criticize(answer, evidence, question)

    findings = state.get("findings", [])
    findings.append(f"Attempt {state.get('retry_count', 0) + 1}: {decision} - {reason}")

    return {
        **state,
        "critic_decision": decision,
        "critic_reason": reason,
        "findings": findings,
    }


async def approve_node(state: AgentState) -> AgentState:
    """Terminal: answer is approved — build citations."""
    evidence = state.get("evidence", [])
    citations = [
        {
            "chunk_id": e["chunk_id"],
            "document_title": e["document_title"],
            "excerpt": e.get("excerpt", "")[:300],
            "effective_date": e.get("effective_date"),
            "version_label": e.get("version_label"),
            "combined_score": e.get("combined_score", 0.0),
        }
        for e in evidence
    ]
    return {
        **state,
        "final_answer": state.get("generated_answer", ""),
        "answer_status": "approved",
        "citations": citations,
    }


async def abstain_node(state: AgentState) -> AgentState:
    """Terminal: answer cannot be verified or has contradiction — escalate."""
    decision = state.get("critic_decision", "abstain")
    reason = state.get("critic_reason", "")
    evidence = state.get("evidence", [])
    citations = [
        {
            "chunk_id": e["chunk_id"],
            "document_title": e["document_title"],
            "excerpt": e.get("excerpt", "")[:300],
            "effective_date": e.get("effective_date"),
            "version_label": e.get("version_label"),
            "combined_score": e.get("combined_score", 0.0),
        }
        for e in evidence
    ]

    if decision == "conflict" or "conflict" in reason.lower() or "contradiction" in reason.lower():
        # Case 2: Contradiction / Conflict across multiple documents
        abstain_msg = (
            "I cannot determine which information is correct because conflicting data was found in our policy documents:\n\n"
            f"{reason}\n\n"
            "Because there is an active contradiction between these documents and I cannot independently prove which figure is currently valid, "
            "I have forwarded this conflict to the bank administrator in the Resolution Center for official review and clarification."
        )
    else:
        # Case 3: Information Not Found in Uploaded Documents
        from app.agents.retriever import get_checked_documents_summary
        checked_titles = await get_checked_documents_summary()
        docs_list = "\n".join(f"• {t}" for t in checked_titles[:8])
        if len(checked_titles) > 8:
            docs_list += f"\n• ...and {len(checked_titles) - 8} other bank policy documents"

        abstain_msg = (
            "I am unable to answer your question because no data related to this question was found in our uploaded bank policy documents.\n\n"
            f"I searched across the following bank documents:\n{docs_list}\n\n"
            "None of these documents contain verified policy information covering your inquiry. "
            "I have forwarded your question to the bank administrator in the Resolution Center "
            "so an admin can review it and either provide the verified answer in the Priority Document or upload a new policy document."
        )

    return {
        **state,
        "final_answer": abstain_msg,
        "answer_status": "abstained",
        "citations": citations,
    }


async def retry_synthesizer_node(state: AgentState) -> AgentState:
    """Retry synthesis with hint about what went wrong."""
    retry_count = state.get("retry_count", 0) + 1
    question = state["question"]
    evidence = state.get("evidence", [])
    critic_reason = state.get("critic_reason", "")

    # Add hint to the question for retry
    refined_question = (
        f"{question}\n\n[Note: Previous answer was rejected because: {critic_reason}. "
        "Please be more precise and stick strictly to the evidence.]"
    )
    answer = await synthesize(refined_question, evidence)
    return {
        **state,
        "generated_answer": answer,
        "retry_count": retry_count,
    }


# ─── Conditional routing ──────────────────────────────────
def route_after_critic(state: AgentState) -> str:
    decision = state.get("critic_decision", "abstain")
    retry_count = state.get("retry_count", 0)

    if decision == "approve":
        return "approve"
    elif decision in ("conflict", "not_found"):
        return "abstain"
    elif retry_count < MAX_RETRIES:
        return "retry"
    else:
        return "abstain"


# ─── Build graph ──────────────────────────────────────────
def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("retrieve",          retriever_node)
    graph.add_node("synthesize",        synthesizer_node)
    graph.add_node("criticize",         critic_node)
    graph.add_node("approve",           approve_node)
    graph.add_node("abstain",           abstain_node)
    graph.add_node("retry_synthesize",  retry_synthesizer_node)

    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve",         "synthesize")
    graph.add_edge("synthesize",       "criticize")
    graph.add_conditional_edges(
        "criticize",
        route_after_critic,
        {
            "approve": "approve",
            "retry":   "retry_synthesize",
            "abstain": "abstain",
        }
    )
    graph.add_edge("retry_synthesize", "criticize")
    graph.add_edge("approve",          END)
    graph.add_edge("abstain",          END)

    return graph


_compiled_graph = build_graph().compile()


# ─── Public entry point ───────────────────────────────────
async def run_graph(
    question: str,
    user_id: str = "",
    conversation_id: str = "",
) -> dict[str, Any]:
    """
    Run the full multi-agent pipeline for a question.
    Returns the final AgentState dict.
    """
    initial_state: AgentState = {
        "question": question,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "evidence": [],
        "retry_count": 0,
        "findings": [],
    }

    try:
        result = await _compiled_graph.ainvoke(initial_state)
        return result
    except Exception as exc:
        return {
            "question": question,
            "final_answer": f"System error: {exc}",
            "answer_status": "error",
            "citations": [],
            "critic_decision": None,
            "critic_reason": str(exc),
            "findings": [],
            "evidence": [],
            "retry_count": 0,
        }
