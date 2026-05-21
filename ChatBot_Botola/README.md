# 🏟️ Botola Pro AI Chatbot — v4.0

> An intelligent, production-ready chatbot for Moroccan football ticketing.  
> Powered by **Hybrid RAG** (BM25 + FAISS) · **Cross-Encoder Reranking** · **Mistral / Ollama / OpenRouter** · **FastAPI**

---

## ✨ Features

| Feature | Details |
|---|---|
| **Hybrid Retrieval** | BM25 keyword search + FAISS semantic search merged via Reciprocal Rank Fusion |
| **Cross-Encoder Reranker** | Re-scores retrieved chunks for highest-quality LLM context |
| **Embedding-based Intent Classifier** | Semantic classification — handles Darija, Arabic, French, English |
| **Query Rewriting** | Uses conversation history to resolve pronouns/follow-ups for RAG |
| **Multi-Provider LLM** | Mistral API · Ollama (local) · OpenRouter — switchable via `.env` |
| **Streaming Responses** | SSE endpoint `/api/chat/stream` for real-time token output |
| **WebSocket Support** | Real-time chat via `/ws/{uuid}` |
| **Multilingual Formatter** | DB results formatted in EN / FR / AR |
| **Conversation Memory** | Redis (with in-memory fallback) |
| **Guardrails** | Input safety · Output hallucination check · Prompt injection detection |
| **Structured Logging** | JSON logs across all modules |

---

## 🏗️ Architecture

```
User Query
    │
    ▼
[Guardrails: Input Check]
    │
    ▼
[Query Rewriter] ◄── conversation history
    │
    ▼
[Intent Classifier] (embedding-based)
    │
    ├── static ──► [Hybrid Search: BM25 + FAISS] ──► [Score Filter] ──► [Reranker]
    │
    ├── dynamic ──► [QueryBuilder → SQLite DB]
    │
    └── unknown ──► RAG fallback
    │
    ▼
[LLM Gateway] (Mistral / Ollama / OpenRouter)
    │
    ▼
[Guardrails: Output Check]
    │
    ▼
[ActionRouter] → Frontend Response
```

---

## 📁 Project Structure

```
ChatBot_Botola/
├── main.py                    # FastAPI app, endpoints, lifespan
├── requirements.txt
├── .env                       # API keys & config
├── docker-compose.yml
├── data/
│   ├── botola_pro.db          # SQLite database
│   ├── raw/                   # Stadium documents (txt/pdf)
│   └── processed/             # FAISS index + chunks.json
├── scripts/
│   └── seed_database.py       # Seed users, matches, tickets
└── src/
    ├── config.py              # All configuration constants
    ├── logger.py              # Structured JSON logging
    ├── intent_classifier.py   # Embedding-based intent classification
    ├── rag_engine.py          # Full RAG pipeline (build / load / answer)
    ├── hybrid_retriever.py    # BM25 + FAISS + RRF
    ├── reranker.py            # Cross-encoder reranking
    ├── chunker.py             # Sentence-aware text chunking
    ├── embedder.py            # SentenceTransformer embeddings
    ├── vector_store.py        # FAISS index wrapper
    ├── document_loader.py     # PDF / TXT / MD loader
    ├── chat_orchestrator.py   # Main pipeline coordinator
    ├── llm_gateway.py         # Unified LLM interface (+ streaming)
    ├── query_builder.py       # DB query logic + team alias table
    ├── response_formatter.py  # EN/FR/AR response templates
    ├── memory.py              # Conversation memory (Redis / in-memory)
    ├── guardrails.py          # Safety checks
    ├── action_router.py       # Route to map / push / human handoff
    └── db_connector.py        # SQLAlchemy DB interface
```

---

## 🚀 Quick Start

### Step 1 — Clone & Create Virtual Environment

```powershell
# PowerShell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

```cmd
# Command Prompt
python -m venv venv
venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 2 — Configure Environment

Edit `.env` to choose your LLM provider:

```env
# Option A: Local Ollama (free, private)
LLM_PROVIDER=ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=mistral:7b

# Option B: Mistral API
LLM_PROVIDER=mistral
MISTRAL_API_KEY=your_key_here
MISTRAL_MODEL=mistral-medium

# Option C: OpenRouter
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=mistralai/mistral-7b-instruct

# CORS (comma-separated allowed origins)
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
```

### Step 3 — Seed the Database

```powershell
python scripts/seed_database.py
```

**Expected output:**
```
✓ Database seeded successfully!
  Users: 4
  Matches: 4
  Tickets: 3
  Transactions: 1
```

### Step 4 — Build the RAG Index

```powershell
python -c "from src.rag_engine import RAGEngine; e = RAGEngine(); e.build(); print(f'Vectors: {e.store.index.ntotal}')"
```

**Expected output:**
```
Loading embedding model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
Model loaded. Embedding dimension: 384
BM25 index built
Built index with N vectors
Saved index to data/processed/faiss_index.bin
Vectors: N
```

> ℹ️ The index is saved to disk. You only need to rebuild it when documents in `data/raw/` change.

### Step 5 — Start the Server

```powershell
uvicorn main:app --reload --port 8000
```

---

## 🧪 Testing the API

Open a **new terminal** with the venv activated.

### Health Check
```powershell
curl http://localhost:8000/api/health
```
```json
{"status":"ok","version":"4.0.0","components":{"rag":true,"llm":"mistral","memory":"in-memory"}}
```

### Static Query (RAG — stadium rules)
```powershell
curl.exe -X POST http://localhost:8000/api/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u_buyer_001\",\"session_id\":\"s1\",\"message\":\"Can I bring a bag?\"}"
```

### Dynamic Query (Database — live ticket data)
```powershell
curl.exe -X POST http://localhost:8000/api/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u_buyer_001\",\"session_id\":\"s1\",\"message\":\"Where is my seat?\"}"
```
**Expected:** Seat info for Raja vs MAS — Zone 04, Row B, Seat 112.

### Arabic Query
```powershell
curl.exe -X POST http://localhost:8000/api/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u_buyer_001\",\"session_id\":\"s1\",\"message\":\"متى تفتح بوابات الملعب؟\"}"
```

### Streaming Response (SSE)
```powershell
curl.exe -N -X POST http://localhost:8000/api/chat/stream ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u_buyer_001\",\"session_id\":\"s1\",\"message\":\"Can I bring food?\"}"
```
Returns `data: {"token": "..."}` events as they stream in.

### Debug: Classify an Intent
```powershell
curl "http://localhost:8000/api/debug/intent?message=Where+is+my+seat"
```

### Test UI (Browser)
```
http://localhost:8000/chatbot-test
```
Click any test case in the left sidebar. Toggle **dark mode** and **debug panel** from the header.

---

## 🌐 WebSocket

Connect with a **valid UUID** as `client_id`:

```javascript
const ws = new WebSocket("ws://localhost:8000/ws/550e8400-e29b-41d4-a716-446655440000");
ws.send(JSON.stringify({
  user_id: "u_buyer_001",
  session_id: "my-session",
  message: "Show my tickets",
  language: "auto"
}));
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

> ⚠️ Non-UUID `client_id` values are rejected with code `1008`.

---

## ⚙️ Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `ollama` · `mistral` · `openrouter` |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `mistral:7b` | Model tag |
| `MISTRAL_API_KEY` | — | Mistral API key |
| `MISTRAL_MODEL` | `mistral-medium` | Mistral model name |
| `OPENROUTER_API_KEY` | — | OpenRouter API key |
| `OPENROUTER_MODEL` | `mistralai/mistral-7b-instruct` | OpenRouter model |
| `REDIS_URL` | — | Redis URL (optional, falls back to in-memory) |
| `MAX_TOKENS` | `512` | Max LLM output tokens |
| `TEMPERATURE` | `0.3` | LLM temperature (lower = more deterministic) |
| `ALLOWED_ORIGINS` | `http://localhost:3000,...` | Comma-separated CORS origins |

---

## 🐳 Docker

```powershell
docker-compose up --build
```

The compose file starts both the chatbot service and a Redis container.

---

## 📊 API Response Format

```json
{
  "type": "chat_reply",
  "message": "Your seat is Zone 04, Row B, Seat 112 at Stade Mohammed V.",
  "data": {},
  "actions": [{"label": "View Stadium Map", "action": "open_map", "url": "/maps/..."}],
  "sources": ["live_db"],
  "metadata": {
    "intent": "seat_location",
    "confidence": 0.91,
    "language": "en",
    "route": "dynamic",
    "processing_time_ms": 312,
    "llm_tokens": 48
  }
}
```

---

## 🔒 Guardrails

| Check | What it catches |
|---|---|
| **Input: Forbidden topics** | `betting`, `gambling`, `odds`, `wager` |
| **Input: Prompt injection** | `ignore previous instructions`, `system prompt`, template injections |
| **Output: Hallucination** | Seat numbers / prices not backed by DB |
| **Output: Uncertainty** | LLM says "I don't know" → escalated to human handoff |
| **Output: Sanitisation** | Strips system prompt leakage from LLM output |

---

## 🧩 Supported Intents

| Route | Intents |
|---|---|
| **Static (RAG)** | `bag_policy` · `gate_time` · `prohibited_items` · `food_policy` · `parking` · `accessibility` · `faq` · `smalltalk` |
| **Dynamic (DB)** | `my_tickets` · `seat_location` · `ticket_status` · `ticket_verification` · `transfer_ticket` · `match_time` · `price_check` · `buy_ticket` |
