# RepoAudit

Automated reproducibility analysis for machine learning research repositories using AST-based static analysis and LLM-powered semantic auditing.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

## What It Does

RepoAudit scans public GitHub ML repositories and produces a **reproducibility score (0–100)** across six categories:

| Category | Weight | What's Checked |
|----------|--------|----------------|
| Environment | 20% | Pinned `requirements.txt`, `environment.yml`, or `Dockerfile` |
| Determinism | 20% | AST-verified seeding for PyTorch, NumPy, Random, TensorFlow |
| Datasets | 20% | Absence of hardcoded local paths, documented download links |
| Semantic | 20% | AI-verified alignment between README and repo structure |
| Execution | 10% | Presence of standard entry points (`train.py`, `Makefile`, etc.) |
| Documentation | 10% | README sections for Installation, Usage, Datasets |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, Tailwind CSS, Recharts, Lucide React |
| Backend API | FastAPI (Python 3.11+) |
| Task Queue | Celery + Redis (sidecar) |
| Analysis | Python `ast` module, `libcst` |
| AI Layer | Groq API (Llama-3-70B) |
| Database | PostgreSQL via Supabase |
| Deployment | HF Spaces (backend), Vercel (frontend) |

## Project Structure

```
RepoAudit/
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env.example
│   ├── pyproject.toml
│   ├── main.py              # FastAPI entry point
│   ├── config.py             # Pydantic settings
│   ├── db.py                 # Supabase client
│   ├── models.py             # Pydantic schemas
│   ├── worker.py             # Celery config
│   ├── tasks.py              # Async audit task
│   ├── routers/
│   │   └── audit.py          # /api/v1/audit endpoints
│   ├── engine/
│   │   ├── cloner.py         # Git clone + cleanup
│   │   ├── ast_auditor.py    # Determinism checks (AST)
│   │   ├── path_auditor.py   # Hardcoded path detection
│   │   ├── dependency_auditor.py  # Dependency analysis
│   │   ├── semantic_auditor.py    # LLM README audit
│   │   └── scoring.py        # Weighted score computation
│   └── tests/
│       ├── test_ast_auditor.py
│       ├── test_path_auditor.py
│       ├── test_dependency_auditor.py
│       └── test_scoring.py
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── .env.local.example
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx          # Main audit page
│   │   └── audit/[id]/page.tsx   # Result permalink
│   ├── components/
│   │   ├── AuditForm.tsx
│   │   ├── ScoreCard.tsx     # Circular gauge
│   │   ├── RadarChart.tsx    # 6-axis category chart
│   │   ├── FixFeed.tsx       # Prioritized issue list
│   │   └── StatusIndicator.tsx   # Progress stepper
│   └── lib/
│       └── api.ts            # Typed API client
├── docker-compose.yml
└── LICENSE
```

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 20+
- Redis (or use Docker)
- [Supabase](https://supabase.com) account (free tier)
- [Groq](https://console.groq.com) API key (free tier)

### Database Setup

Run this in your Supabase SQL editor:

```sql
CREATE TABLE IF NOT EXISTS repositories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT UNIQUE NOT NULL,
    owner TEXT,
    name TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_id UUID REFERENCES repositories(id) ON DELETE SET NULL,
    commit_hash TEXT NOT NULL,
    score INTEGER CHECK (score >= 0 AND score <= 100),
    report_json JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_commit ON audits(commit_hash);
CREATE INDEX IF NOT EXISTS idx_audit_repo ON audits(repo_id);
```

### Option A: Docker (recommended)

```bash
# 1. Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env with your Supabase + Groq keys

# 2. Start everything
docker compose up --build
```

Frontend at `http://localhost:3000`, API at `http://localhost:7860`.

### Option B: Local Development

```bash
# Backend
cd backend
cp .env.example .env
# Edit .env with your keys
pip install -r requirements.txt
redis-server &
celery -A worker worker --loglevel=info &
uvicorn main:app --reload --port 7860

# Frontend (separate terminal)
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

### Running Tests

```bash
cd backend
pytest
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/audit` | Submit a repo URL for analysis |
| `GET` | `/api/v1/audit/{id}` | Get full audit result |
| `GET` | `/api/v1/audit/{id}/status` | Poll task progress |
| `GET` | `/health` | Health check |

**Submit example:**
```bash
curl -X POST http://localhost:7860/api/v1/audit \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/owner/repo"}'
```

## How Caching Works

1. On submission, the API resolves the repo's latest `commit_hash` via `git ls-remote`
2. If that hash exists in Redis or Postgres, the cached report is returned instantly (<200ms)
3. Otherwise, a Celery task clones the repo (depth=1) and runs the full analysis pipeline
