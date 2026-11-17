"""
Agent 1: Retriever Agent — Hybrid BM25 + Semantic Search.

Retrieves the top-K most relevant document chunks using:
  - BM25 keyword scoring (rank(1))
  - Cosine similarity on embeddings (rank(2))
  - Reciprocal Rank Fusion (RRF) to combine both
"""
from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from typing import Any

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
import app.models  # ensure models are loaded
from app.models.document import Document, DocumentChunk
from app.services.embedding import embedding_service


# ─── Stopwords ───────────────────────────────────────────
STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down",
    "during", "each", "few", "for", "from", "further", "had", "hadn't", "has",
    "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
    "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's",
    "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it",
    "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other",
    "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "shan't",
    "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves", "tell", "give", "please", "know", "want", "bank",
    "meridian", "national", "mnb", "policy", "policies",
}

GENERIC_FINANCE_WORDS = {
    "loan", "loans", "account", "accounts", "rate", "rates", "interest", "tenure",
    "repayment", "fee", "fees", "charge", "charges", "deposit", "deposits",
    "balance", "penalty", "amount", "limit", "limits", "minimum", "maximum",
    "criteria", "eligibility", "eligible", "apply", "open", "opening",
    "service", "services", "scheme", "schemes", "bank", "banking",
    "customer", "customers", "detail", "details", "rule", "rules",
    "guideline", "guidelines", "information", "info", "policy", "policies",
    "required", "requirements", "period", "time", "status", "type", "types",
    "document", "documents", "id", "card", "cards", "number", "verification",
}


# ─── BM25 ────────────────────────────────────────────────
def _tokenize(text: str) -> list[str]:
    return re.findall(r'\w+', text.lower())


def _bm25_score(query_tokens: list[str], doc_tokens: list[str], avg_dl: float,
                k1: float = 1.5, b: float = 0.75) -> float:
    dl = len(doc_tokens)
    tf_map: dict[str, int] = defaultdict(int)
    for t in doc_tokens:
        tf_map[t] += 1

    score = 0.0
    for qt in query_tokens:
        tf = tf_map.get(qt, 0)
        if tf == 0:
            continue
        idf = 1.0  # simplified IDF (full corpus IDF requires all docs)
        num = tf * (k1 + 1)
        den = tf + k1 * (1 - b + b * dl / max(avg_dl, 1))
        score += idf * (num / den)
    return score


def _rrf(bm25_ranks: dict[str, int], sem_ranks: dict[str, int],
          k: int = 60) -> dict[str, float]:
    chunk_ids = set(bm25_ranks) | set(sem_ranks)
    scores: dict[str, float] = {}
    for cid in chunk_ids:
        r1 = bm25_ranks.get(cid, len(bm25_ranks) + 1)
        r2 = sem_ranks.get(cid, len(sem_ranks) + 1)
        scores[cid] = 1 / (k + r1) + 1 / (k + r2)
    return scores


async def get_checked_documents_summary() -> list[str]:
    """Return distinct titles of all published documents in the knowledge base."""
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(Document.title)
            .where(Document.status == "published")
            .order_by(Document.title)
        )
        titles = [t for t in res.scalars().all() if t]
        return titles


# ─── Main retriever function ──────────────────────────────
async def retrieve(question: str, top_k: int = 5) -> list[dict[str, Any]]:
    """
    Run hybrid retrieval for a question.
    Returns list of evidence dicts sorted by combined relevance score.
    Applies timestamp comparison if a Priority Document match is found.
    """
    async with AsyncSessionLocal() as db:
        from sqlalchemy.orm import selectinload
        # Load all chunks from published documents with their parent document loaded
        result = await db.execute(
            select(DocumentChunk)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(Document.status == "published")
            .options(selectinload(DocumentChunk.document))
        )
        all_chunks = result.scalars().all()

        # Fallback if no published docs yet: load any available chunks
        if not all_chunks:
            fallback_res = await db.execute(select(DocumentChunk).options(selectinload(DocumentChunk.document)))
            all_chunks = fallback_res.scalars().all()

    if not all_chunks:
        return []

    # Build query embedding
    q_emb = (await embedding_service.encode([question]))[0]
    query_tokens = _tokenize(question)
    substantive_tokens = [w for w in query_tokens if w not in STOPWORDS and len(w) > 1]
    # For BM25, use substantive tokens so conversational stopwords don't trigger false matches
    bm25_query_tokens = substantive_tokens if substantive_tokens else query_tokens
    avg_dl = sum(c.word_count or len(_tokenize(c.content)) for c in all_chunks) / len(all_chunks)

    # Score with BM25 (include title and section to boost title keyword matches)
    bm25_scores: list[tuple[str, float]] = []
    for chunk in all_chunks:
        full_text = f"{chunk.document_title or ''} {chunk.section_title or ''} {chunk.content}"
        doc_tokens = _tokenize(full_text)
        s = _bm25_score(bm25_query_tokens, doc_tokens, avg_dl)
        bm25_scores.append((chunk.id, s))
    bm25_scores.sort(key=lambda x: x[1], reverse=True)
    bm25_ranks = {cid: i + 1 for i, (cid, _) in enumerate(bm25_scores)}

    # Score with cosine similarity
    sem_scores: list[tuple[str, float]] = []
    chunk_map = {c.id: c for c in all_chunks}
    for chunk in all_chunks:
        if chunk.embedding_json:
            try:
                emb = json.loads(chunk.embedding_json)
                sim = embedding_service.cosine_similarity(q_emb, emb)
                sem_scores.append((chunk.id, sim))
            except Exception:
                sem_scores.append((chunk.id, 0.0))
        else:
            sem_scores.append((chunk.id, 0.0))
    sem_scores.sort(key=lambda x: x[1], reverse=True)
    sem_ranks = {cid: i + 1 for i, (cid, _) in enumerate(sem_scores)}

    # Check overall relevance: if question has substantive tokens and no chunk matches keyword and max semantic similarity is low
    max_bm25 = max((s for _, s in bm25_scores), default=0.0)
    max_sem = max((s for _, s in sem_scores), default=0.0)
    if substantive_tokens and max_bm25 <= 0.0 and max_sem < 0.30:
        return []

    # ─── Demo Gating for 5 Specific Documents ─────────────────
    q_lower = question.lower()

    # 1. Check if the question is answered in the Priority Document
    has_priority_match = False
    try:
        from app.services.priority_doc import _get_priority_doc_path, parse_priority_entries
        p_path = _get_priority_doc_path()
        if p_path.exists():
            p_text = p_path.read_text(encoding="utf-8", errors="replace")
            p_entries = parse_priority_entries(p_text)
            q_words = set(re.findall(r'\w+', q_lower)) - STOPWORDS - GENERIC_FINANCE_WORDS
            for entry in p_entries:
                entry_words = set(re.findall(r'\w+', entry["question"].lower())) - STOPWORDS - GENERIC_FINANCE_WORDS
                if q_words and entry_words and len(q_words & entry_words) >= min(2, len(q_words)):
                    has_priority_match = True
                    break
    except Exception:
        pass

    # 2. If not in Priority Document, check for uncovered demo topics
    if not has_priority_match:
        uncovered_topics = [
            "student", "education", "home loan", "housing loan", "mortgage",
            "personal loan", "car loan", "vehicle loan", "auto loan", "two wheeler",
            "credit card", "reward card", "credit cards", "rewards card",
            "locker", "lockers", "safe deposit box", "safe deposit locker",
            "mutual fund", "mutual funds", "share", "stock", "stocks", "demat",
            "trading", "crypto", "bitcoin", "insurance", "forex", "foreign exchange",
            "wire transfer", "swift", "cheque bounce", "salary account", "recipe",
            "weather", "flight", "train", "hotel"
        ]
        if any(re.search(r'\b' + re.escape(u) + r'\b', q_lower) for u in uncovered_topics):
            return []

        # 3. Check if the question belongs to one of the 5 allowed document domains
        doc1_gold = bool(re.search(r'\b(gold|jewellery|jewelry|ornament|ornaments|karat)\b', q_lower))
        doc2_fd = bool(re.search(r'\b(fixed deposit|term deposit|fd|fds|premature withdrawal|deposit)\b', q_lower))
        doc3_savings = bool(re.search(r'\b(saving|savings|sb account|v-kyc)\b', q_lower))
        doc4_card = bool(re.search(r'\b(atm|debit|card|cards|hotlisting|pin)\b', q_lower))
        doc5_current = bool(re.search(r'\b(current|business account|commercial account|proprietorship|partnership|mab)\b', q_lower))

        if not (doc1_gold or doc2_fd or doc3_savings or doc4_card or doc5_current):
            # Not one of the 5 covered policy topics
            return []

    # Combine with RRF
    combined = _rrf(bm25_ranks, sem_ranks)

    # Domain alignment boost: ensure the exact matching document is rank 1
    for cid in combined:
        chk = chunk_map.get(cid)
        if not chk:
            continue
        c_title = (chk.document_title or "").lower()
        if doc1_gold and "gold" in c_title:
            combined[cid] += 0.5
        elif doc2_fd and ("fixed deposit" in c_title or "fd" in c_title):
            combined[cid] += 0.5
        elif doc3_savings and "savings" in c_title and not doc5_current:
            combined[cid] += 0.5
        elif doc5_current and "current" in c_title and not doc3_savings:
            combined[cid] += 0.5
        elif doc4_card and ("debit" in c_title or "atm" in c_title):
            combined[cid] += 0.5

    top_ids = sorted(combined, key=lambda x: combined[x], reverse=True)[:top_k]

    # Helper to parse timestamp from chunk content
    def _extract_chunk_timestamp(content: str) -> datetime | None:
        m = re.search(r'\[TIMESTAMP:\s*([^\]]+)\]', content)
        if m:
            ts_str = m.group(1).strip().replace("UTC", "").strip()
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
                try:
                    from datetime import timezone
                    return datetime.strptime(ts_str, fmt).replace(tzinfo=timezone.utc)
                except Exception:
                    continue
        return None

    # Separate priority document chunks and standard document chunks
    sem_map = dict(sem_scores)
    bm25_map = dict(bm25_scores)
    priority_candidates = []
    normal_candidates = []

    for cid in top_ids:
        chunk = chunk_map.get(cid)
        if not chunk:
            continue
        bm_s = bm25_map.get(cid, 0.0)
        sm_s = sem_map.get(cid, 0.0)
        # Exclude completely unrelated chunks
        if substantive_tokens and bm_s <= 0.0 and sm_s < 0.25:
            continue

        is_priority = (
            chunk.version_label == "PRIORITY"
            or "Priority Document" in (chunk.document_title or "")
        )
        chunk_ts = _extract_chunk_timestamp(chunk.content)

        ev_item = {
            "chunk_id": chunk.id,
            "document_id": chunk.document_id,
            "document_title": chunk.document_title or "Unknown",
            "content": chunk.content,
            "section_title": chunk.section_title,
            "effective_date": chunk.effective_date,
            "version_label": chunk.version_label,
            "bm25_score": round(bm_s, 4),
            "semantic_score": round(sm_s, 4),
            "combined_score": round(combined.get(cid, 0.0), 6),
            "excerpt": chunk.content[:300],
            "is_priority": is_priority,
            "timestamp": chunk_ts.isoformat() if chunk_ts else None,
            "timestamp_dt": chunk_ts,
            "parent_doc": chunk.document,
        }

        if is_priority:
            priority_candidates.append(ev_item)
        else:
            normal_candidates.append(ev_item)

    # ─── Timestamp Comparison Logic ───
    # If there is data in the priority document:
    # Compare its timestamp against any matching standard documents.
    # If any matching standard document was published AFTER the priority timestamp,
    # compare both (newer doc placed alongside priority doc).
    # Otherwise, take data from the priority document with highest precedence!
    if priority_candidates:
        p_ts = priority_candidates[0].get("timestamp_dt")
        newer_docs = []
        if p_ts:
            from datetime import timezone
            for norm in normal_candidates:
                doc_obj = norm.get("parent_doc")
                doc_ts = None
                if doc_obj:
                    doc_ts = doc_obj.published_at or doc_obj.created_at
                if doc_ts and doc_ts.tzinfo is None:
                    doc_ts = doc_ts.replace(tzinfo=timezone.utc)
                if doc_ts and doc_ts > p_ts:
                    norm["is_newer_than_priority"] = True
                    norm["newer_timestamp"] = doc_ts.isoformat()
                    newer_docs.append(norm)

        if newer_docs:
            evidence = newer_docs + priority_candidates + [n for n in normal_candidates if n not in newer_docs]
        else:
            priority_candidates[0]["priority_precedence"] = True
            evidence = priority_candidates + normal_candidates
    else:
        evidence = normal_candidates

    # Clean up non-serializable fields
    for e in evidence:
        e.pop("parent_doc", None)
        e.pop("timestamp_dt", None)

    return evidence[:top_k]
