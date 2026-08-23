# RepoTwin

**RepoTwin** is an engineering-grade code intelligence platform that combines deterministic static analysis (AST/call graph, Git history, risk scoring) with a full RAG (Retrieval-Augmented Generation) pipeline powered by **Code Llama via Ollama**.

It answers the question: *"If I change this function, what breaks in production — and what does the AI say about it?"*

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        React / Vite Frontend                     │
│  RAG Mode Selector │ Model Selector │ Chunk Viewer │ Compare     │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP (Vite proxy → localhost:8000)
┌───────────────────────────▼─────────────────────────────────────┐
│                     FastAPI Backend (Uvicorn)                    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │             Deterministic Analysis Engine                 │   │
│  │  Repository Graph → Call Graph → Risk Scorer             │   │
│  │  Git History → Evidence Retrieval → Evidence Validator    │   │
│  │  Test Impact (tests never counted as production)          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  RAG Pipeline (Exercises 2-4)             │   │
│  │  AST Chunker → Embedding Service → Vector Store           │   │
│  │  RAG Service → Prompt Builder → LLM Service (Ollama)     │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                            │
              ┌─────────────┴───────────────┐
              │                             │
   ┌──────────▼──────────┐     ┌────────────▼────────────┐
   │  Ollama (Code Llama) │     │  Git / GitHub Repos      │
   │  codellama:7b        │     │  Cloned to data/repos/   │
   └─────────────────────┘     └─────────────────────────┘
```

---

## Exercises Mapping

### Exercise 1 — Application + API + Ollama + Code Llama

**Service**: [`backend/app/services/llm_service.py`](backend/app/services/llm_service.py)

- Integrates with **Ollama** via `OLLAMA_BASE_URL` (default: `http://localhost:11434`)
- Default model: **`codellama:7b`** (Code Llama, as required by the assignment)
- Provides `check_ollama_health()` — reports availability without silent fallback
- If Code Llama is unavailable, the integration is reported as unavailable (never substituted silently)
- `qwen2.5-coder:1.5b` is available as an **explicit optional model** only
- Generates grounded RAG prompts that incorporate deterministic facts (production impact, risk score, direct/indirect callers, affected tests)
- Generates ungrounded non-RAG prompts for side-by-side comparison

**API Endpoints**:
- `GET /health` — reports Ollama availability and available models
- `POST /repositories/engineering-analysis` — run analysis with LLM response (RAG or non-RAG mode)

---

### Exercise 2 — Knowledge Base + Chunking

**Service**: [`backend/app/services/chunking_service.py`](backend/app/services/chunking_service.py)

- Parses Python files using the built-in `ast` module (no external dependencies)
- Produces **code-aware AST chunks** — not line-split or token-split
- Chunk types: `class`, `method`, `function`, `module`
- Each chunk captures:
  - `chunk_id` — unique identifier
  - `chunk_type` — class / method / function / module
  - `name` — symbol name
  - `source_code` — full extracted source text
  - `docstring` — extracted from AST (if present)
  - `start_line`, `end_line` — accurate line numbers
  - `file_path`, `repo_name` — provenance metadata
- Module-level chunks include top-level imports and statements

**API Endpoint**:
- `POST /repositories/index` — triggers AST chunking + vector indexing for a cloned repository

---

### Exercise 3 — Embeddings + Vector Store

**Services**:
- [`backend/app/services/embedding_service.py`](backend/app/services/embedding_service.py)
- [`backend/app/services/vector_store.py`](backend/app/services/vector_store.py)

**Embedding Service**:
- Uses `sentence-transformers` with `all-MiniLM-L6-v2` (384 dimensions)
- Model is configurable via `EMBEDDING_MODEL` environment variable
- Lazy-loads the model on first use to minimize startup time
- Produces **L2-normalized embeddings** for exact cosine similarity via dot product

**Vector Store**:
- Pure NumPy-based — no external vector DB required
- Cosine similarity via dot product on normalized vectors: `np.dot(embeddings, q_vec)`
- Top-k retrieval with similarity scores
- Supports metadata filtering (by `repo_name`, `chunk_type`, etc.)
- File-based persistence: `.json` (metadata) + `.npy` (embeddings) per repository
- Index stored in `backend/data/indexes/` (Git-ignored)

---

### Exercise 4 — RAG Pipeline + APIs

**Service**: [`backend/app/services/rag_service.py`](backend/app/services/rag_service.py)

The RAG orchestrator:
1. Checks if a vector index exists for the repository; if not, builds it
2. Embeds the user's query
3. Retrieves top-k semantically similar AST code chunks
4. Assembles RAG context combining:
   - **Deterministic evidence** (production impact, risk score, direct/indirect callers, affected tests, Git commits)
   - **Retrieved code chunks** with similarity scores
5. Builds the grounded RAG prompt for Code Llama
6. Optionally builds an ungrounded non-RAG prompt for comparison

**API Endpoints (all in [`backend/app/main.py`](backend/app/main.py))**:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Root info with Ollama status |
| `GET` | `/health` | Health check — Ollama, embedding model, service status |
| `GET` | `/repositories/targets` | List pre-configured analysis targets |
| `POST` | `/repositories/index` | Explicit chunk + vector index for a repo |
| `POST` | `/repositories/engineering-analysis` | Full analysis: deterministic + LLM (RAG or non-RAG) |
| `POST` | `/repositories/rag-compare` | Side-by-side RAG vs. non-RAG comparison |

**Request body for `/repositories/engineering-analysis`**:
```json
{
  "repo_url": "https://github.com/psf/requests",
  "symbol": "method:src/requests/models.py:Response.close",
  "use_rag": true,
  "model": "codellama:7b",
  "top_k": 5
}
```

**Response includes**:
- `production_impact`, `direct_callers`, `indirect_callers`, `affected_tests`, `risk_score`, `risk_level` (deterministic, authoritative)
- `llm_response` — Code Llama's grounded answer
- `retrieved_chunks` — AST chunks used with similarity scores
- `validation_result` — evidence validation report

---

### Exercise 5 — Docker + Containerization

**Files**:
- [`backend/Dockerfile`](backend/Dockerfile) — Python 3.11-slim, installs system Git, runs Uvicorn
- [`frontend/Dockerfile`](frontend/Dockerfile) — Multi-stage: Node 20 builder → Nginx serving
- [`docker-compose.yml`](docker-compose.yml) — Orchestrates backend + frontend

**Run with Docker Compose**:
```bash
cp .env.example .env
# Edit .env with your OLLAMA_BASE_URL
docker-compose up --build
```

Services:
- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`

---

## Setup & Running Locally

### Prerequisites

- Python 3.11+
- Node.js 18+
- Git
- [Ollama](https://ollama.ai/) with `codellama:7b` pulled:
  ```bash
  ollama pull codellama:7b
  ```

### Backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
cp ../.env.example ../.env   # edit as needed
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev    # dev server at http://localhost:5173
npm run build  # production build to dist/
```

---

## Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `codellama:7b` | Default LLM model (Code Llama required) |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformer model |
| `REPOSITORIES_DIR` | `backend/data/repos` | Where repos are cloned |
| `INDEXES_DIR` | `backend/data/indexes` | Where vector indexes are stored |
| `BACKEND_PORT` | `8000` | Backend port |
| `FRONTEND_PORT` | `3000` | Frontend port |

---

## Data Flow

```
User Query (repo URL + symbol)
        │
        ▼
1. CLONE / CACHE repository (Git)
        │
        ▼
2. BUILD repository graph (AST + call graph)
        │
        ├──► 3. DETERMINISTIC ANALYSIS
        │        - direct callers (AST)
        │        - indirect callers (BFS traversal)
        │        - test impact (test files, never counted as production)
        │        - risk score (0-100, deterministic)
        │        - Git commit history for symbol
        │
        └──► 4. RAG PIPELINE (if use_rag=True)
                 - AST chunk repository into code-aware chunks
                 - Embed chunks with all-MiniLM-L6-v2
                 - Store in NumPy vector store (cached to disk)
                 - Embed query
                 - Retrieve top-k similar chunks (cosine similarity)
                 - Assemble context (deterministic facts + code chunks)
                 │
                 ▼
             5. CODE LLAMA (Ollama)
                 - Receive grounded RAG prompt
                 - Generate engineering analysis response
                 │
                 ▼
             6. EVIDENCE VALIDATION
                 - Validate LLM claims against deterministic ground truth
                 - Flag numerical discrepancies, unsupported claims
                 │
                 ▼
             7. RESPONSE to Frontend
                 - deterministic metrics (authoritative)
                 - LLM analysis (validated)
                 - retrieved chunks with similarity scores
                 - validation report
```

---

## Authoritative Deterministic Metrics

The deterministic analysis is always authoritative. The LLM supplements — it never overrides.

**Verified regression targets** (these values must always hold):

| Symbol | production | direct | indirect | tests | risk | level |
|--------|-----------|--------|----------|-------|------|-------|
| `method:src/requests/models.py:Response.close` | 12 | 3 | 9 | 34 | 87 | HIGH |
| `method:fastapi/applications.py:FastAPI.include_router` | 0 | 0 | 0 | 60 | 0 | MINIMAL |

**Invariant**: Tests are never counted as production impact.

---

## Testing

Run the full test suite:
```bash
$env:PYTHONPATH="backend"   # PowerShell (Windows)
# or
export PYTHONPATH=backend   # bash (Linux/macOS)

python -m pytest backend/tests/ -v
```

### Test Results (verified)

```
backend/tests/test_rag_pipeline.py::test_ast_chunking                    PASSED
backend/tests/test_rag_pipeline.py::test_embedding_service               PASSED
backend/tests/test_rag_pipeline.py::test_vector_store_similarity_search  PASSED
backend/tests/test_rag_pipeline.py::test_rag_context_and_prompts         PASSED
backend/tests/test_regression.py::test_requests_response_close_regression PASSED
backend/tests/test_regression.py::test_fastapi_include_router_regression  PASSED
backend/tests/test_regression.py::test_flask_regression                   PASSED
backend/tests/test_regression.py::test_tests_never_counted_as_production  PASSED

8 passed in 99.02s
```

---

## Project Structure

```
repotwin/
├── .env.example                          # Environment template
├── .gitignore                            # Excludes repos, indexes, venvs
├── docker-compose.yml                    # Docker orchestration
├── README.md
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py                       # FastAPI app + all endpoints
│       ├── analysis/
│       │   ├── evidence.py               # Deterministic evidence builder
│       │   └── test_impact.py            # Test impact analysis
│       ├── graph/
│       │   ├── call_graph.py             # AST call graph builder
│       │   ├── repository_graph.py       # Repository-level graph
│       │   ├── risk.py                   # Deterministic risk scorer
│       │   ├── typed_graph.py            # Graph data structures
│       │   └── unified_graph.py          # Graph composition
│       ├── services/
│       │   ├── chunking_service.py       # Exercise 2: AST chunker
│       │   ├── embedding_service.py      # Exercise 3: Sentence-transformer
│       │   ├── llm_service.py            # Exercise 1: Code Llama / Ollama
│       │   ├── rag_service.py            # Exercise 4: RAG orchestrator
│       │   ├── repository_service.py     # Repo clone + caching
│       │   └── vector_store.py           # Exercise 3: NumPy vector store
│       └── validation/
│           └── evidence_validator.py     # LLM response validator
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.js                    # Vite proxy config
│   └── src/
│       ├── App.jsx                       # Main React app
│       └── App.css                       # Styles
│
└── backend/tests/
    ├── test_rag_pipeline.py              # Tests for Exercises 2-4
    └── test_regression.py               # Deterministic regression tests
```

---

## Code Llama / Ollama Integration Notes

- **Required model**: `codellama:7b` (as per assignment)
- **No silent substitution**: If Code Llama is unavailable, the API reports `ollama_available: false` and explains the error. It does NOT claim success using a different model.
- **Optional alternative**: `qwen2.5-coder:1.5b` can be explicitly selected in the frontend model dropdown.
- **Configurable endpoint**: Set `OLLAMA_BASE_URL` — never hardcoded IPs.

To check Ollama status:
```bash
curl http://localhost:8000/health
```

---

## Git Notes

- **Do not commit**: `.venv/`, `node_modules/`, `.env`, `__pycache__/`, `backend/data/repos/`, `backend/data/indexes/`, `frontend/dist/`
- All changes are Linux-compatible (POSIX paths enforced via `.as_posix()`)
- Pull into Ubuntu VM and run as-is: `git pull && uvicorn app.main:app`
