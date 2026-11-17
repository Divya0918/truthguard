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

## 📂 Project Structure

```
truthguard-v2/
├── backend/                    # FastAPI + LangGraph backend
│   ├── app/
│   │   ├── agents/             # 3 LangGraph agents + orchestration graph
│   │   │   ├── retriever.py    # Agent 1: Hybrid BM25 + Semantic retrieval
│   │   │   ├── synthesizer.py  # Agent 2: RAG answer generation
│   │   │   ├── critic.py       # Agent 3: NLI verification
│   │   │   └── graph.py        # LangGraph state machine
│   │   ├── api/                # FastAPI routers
│   │   │   ├── auth.py         # JWT auth (login / register / me)
│   │   │   ├── chat.py         # Customer chat endpoint
│   │   │   ├── admin_docs.py   # Document upload & ingestion
│   │   │   ├── admin_history.py # Chat history review
│   │   │   └── admin_resolution.py # Resolution & clarification workflow
│   │   ├── core/
│   │   │   ├── config.py       # Pydantic settings (from .env)
│   │   │   ├── database.py     # Async SQLAlchemy engine
│   │   │   └── security.py     # JWT, password hashing
│   │   ├── models/             # SQLAlchemy ORM models
│   │   ├── services/
│   │   │   ├── ingestion.py    # Text extraction + chunking + embedding
│   │   │   ├── embedding.py    # Sentence-transformers / mock
│   │   │   └── llm.py          # LLM service (Mock / OpenAI / Ollama)
│   │   └── main.py             # App factory + lifespan startup
│   ├── data/policies/          # 22 synthetic MNB policy documents
│   ├── scripts/                # DB seed + cleanup utilities
│   ├── requirements.txt
│   └── .env.example
│
└── frontend/                   # React 18 + TypeScript + Vite + Tailwind
    ├── src/
    │   ├── api/client.ts       # Typed API client
    │   ├── hooks/useAuth.tsx   # Auth context
    │   ├── pages/
    │   │   ├── Login.tsx
    │   │   ├── customer/Chat.tsx       # Customer chatbot UI
    │   │   └── admin/
    │   │       ├── Documents.tsx       # Document management
    │   │       ├── ChatHistory.tsx     # Chat history review
    │   │       └── Resolution.tsx      # Resolution center
    │   ├── layouts/AdminLayout.tsx     # Admin sidebar layout
    │   └── types/index.ts      # TypeScript type definitions
    └── package.json
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+ 
- Node.js 18+
- Git

### 1. Clone the repo
```bash
git clone https://github.com/Divya0918/truthguard.git
cd truthguard
```

### 2. Backend Setup
```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# OR Activate (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
copy .env.example .env    # Windows
# cp .env.example .env    # Mac/Linux

# (Optional) Edit .env to configure LLM provider
# Default: LLM_PROVIDER=mock (no API key needed)
```

### 3. Start the Backend
```bash
# From the backend/ directory, with venv activated:
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The first startup will:
- Create the SQLite database (`truthguard.db`)
- Seed admin and demo customer accounts
- Ingest all 22 synthetic policy documents automatically

Backend API available at: **http://localhost:8000**  
Interactive API docs: **http://localhost:8000/docs**

### 4. Frontend Setup
```bash
# In a NEW terminal:
cd frontend
npm install
npm run dev
```

Frontend available at: **http://localhost:5173**

---

## 🔑 Demo Credentials

| Role | Email | Password |
|------|-------|----------|
| **Admin** | admin@demo.com | Admin@123456 |
| **Customer** | customer@demo.com | Customer@123 |

---

## ⚙️ Configuration (`.env`)

```env
# LLM Provider: mock | openai | ollama
LLM_PROVIDER=mock

# OpenAI (optional)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Ollama (optional — run ollama locally)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2

# Embedding: mock | local (sentence-transformers) | openai
EMBEDDING_PROVIDER=local
```

**Default**: `LLM_PROVIDER=mock` — works with zero API keys. Mock LLM generates intelligent placeholder responses using the retrieved evidence.

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

## 🏗️ Architecture

```
┌──────────────┐    REST API     ┌─────────────────────────────────┐
│   React UI   │ ◄────────────► │   FastAPI Application           │
│  (Port 5173) │                │   (Port 8000)                   │
└──────────────┘                │                                 │
                                │  ┌─────────────────────────┐   │
                                │  │   LangGraph Pipeline    │   │
                                │  │  retrieve → synthesize  │   │
                                │  │  → criticize → [approve │   │
                                │  │  /retry/abstain]        │   │
                                │  └─────────────────────────┘   │
                                │                                 │
                                │  ┌──────────┐ ┌─────────────┐  │
                                │  │ SQLite   │ │  Embeddings │  │
                                │  │   DB     │ │  (local)    │  │
                                │  └──────────┘ └─────────────┘  │
                                └─────────────────────────────────┘
```

---

## 📝 License

MIT — Built for academic demonstration purposes. All banking data is synthetic.
