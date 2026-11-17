# TruthGuard — Multi-Agent Banking Intelligence System

> **Verified. Grounded. Trustworthy.**  
> A RAG-based banking policy assistant that verifies every answer through a 3-agent LangGraph pipeline before serving it to customers.

---

## 🏦 Overview

TruthGuard is a full-stack AI system built for **Meridian National Bank (MNB)** that answers customer banking queries — about Fixed Deposits, Gold Loans, Savings Accounts, KYC, and more — by:

1. **Retrieving** relevant policy passages (Hybrid BM25 + Semantic search)
2. **Synthesizing** a grounded answer (RAG with LLM)
3. **Criticizing** the answer with NLI verification (approve / retry / abstain)
4. **Escalating** unverifiable answers to human admins via the Resolution Center

---

## 🤖 Three-Agent Pipeline

```
Customer Question
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│                    LangGraph Orchestrator                │
│                                                         │
│  [Agent 1: Retriever]                                   │
│   Hybrid BM25 + Sentence-Transformer semantic search    │
│   Reciprocal Rank Fusion (RRF) for re-ranking           │
│      │                                                  │
│      ▼                                                  │
│  [Agent 2: Synthesizer]                                 │
│   Grounded RAG answer using retrieved evidence only     │
│   LLM: Mock (default) / OpenAI / Ollama                 │
│      │                                                  │
│      ▼                                                  │
│  [Agent 3: Critic]                                      │
│   NLI verification — checks if answer is supported     │
│   Decision: APPROVE → serve | RETRY → re-synthesize     │
│             ABSTAIN → escalate to Resolution Center     │
└─────────────────────────────────────────────────────────┘
      │
      ▼
 Final Answer (with citations)  OR  Resolution Task created
```

---

## 📊 Features

### Customer Panel
- 💬 **Conversational chat** with banking policy AI
- 📚 **Evidence citations** — every answer shows the source policy document
- 🔍 **Verification badges** — Approved / Abstained status shown per answer
- 📜 **Conversation history** with full message threads

### Admin Panel
- 📄 **Document Management** — upload, ingest, and manage policy documents
- 🕐 **Chat History** — review all customer conversations and agent decisions
- ⚖️ **Resolution Center** — handle escalated/unverified questions, add clarifications

### AI Pipeline
- **Hybrid search**: BM25 keyword + Sentence-Transformer semantic search fused via Reciprocal Rank Fusion (RRF)
- **Grounded RAG**: Synthesizer is strictly constrained to only use retrieved evidence
- **NLI Critic**: Independent verification with retry loop (max 2 retries before abstaining)
- **Escalation workflow**: Abstained answers create resolution tasks for admin review

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, SQLAlchemy (async), aiosqlite |
| AI Orchestration | LangGraph |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`) |
| LLM | Mock / OpenAI / Ollama (configurable) |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Auth | JWT (python-jose) |
| Database | SQLite (dev) / PostgreSQL (prod-ready) |

---

## 📜 Synthetic Policy Documents

The system ships with **22 pre-loaded synthetic banking policy documents** covering:

- Fixed Deposit interest rates (v1 archived + v2 current — demonstrates policy versioning conflict detection)
- Gold Loan rates & eligibility
- Savings & Current Account policies
- Personal & Home Loan eligibility
- KYC / AML requirements
- Senior citizen benefits
- Banking fees & charges
- Complaint & grievance resolution
- Digital banking guidelines

---

## 📝 License

MIT — Built for academic demonstration purposes. All banking data is synthetic.
