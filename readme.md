# RepoAudit

Automated reproducibility analysis for machine learning research repositories (supporting Python, R, Julia, and Jupyter Notebooks) using AST-based static analysis and LLM-powered semantic auditing.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

**Live:** [repo-audit.vercel.app](https://repo-audit.vercel.app) · **API:** [repoaudit-api.onrender.com](https://repoaudit-api.onrender.com/health)

## What It Does

RepoAudit scans public GitHub ML repositories and produces a **reproducibility score (0–100)** across six categories:

| Category | Weight | What's Checked |
|----------|--------|----------------|
| Environment | 20% | Pinned dependencies, Dockerfile, **Hardware Fingerprinting Detection** |
| Determinism | 20% | AST-verified seeding, **Non-deterministic shuffling detection** |
| Datasets | 20% | No hardcoded paths, **Data Provenance (URL liveness, gated datasets)** |
| Semantic | 20% | AI-verified alignment between README and repo structure |
| Execution | 10% | Presence of standard entry points (`train.py`, `Makefile`, etc.) |
| Documentation | 10% | README sections for Installation, Usage, Datasets |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, Tailwind CSS, Recharts, Lucide React |
| Backend API | FastAPI (Python 3.11+) |
| Task Queue | Celery + Valkey (local) / Upstash Redis (production) |
| Analysis | Python `ast` module, **`libcst` (for deterministic rewriting)**, Tree-sitter (R, Julia), Jupyter parsing, cross-file import graph |
| AI Layer | Hugging Face API (Llama-3.3-70B) |
| Remediation | Native Python `libcst` & `difflib` |
| Database | PostgreSQL via Supabase |
| Cache | Valkey protocol cache (local Valkey, Upstash Redis in production) |
| Deployment | Render (backend), Vercel (frontend) |

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
│   ├── worker.py             # Celery config (Upstash TLS)
│   ├── tasks.py              # Async audit task
│   ├── routers/
│   │   └── audit.py          # /api/v1/audit endpoints
│   ├── engine/
│   │   ├── cloner.py         # Git clone + cleanup
│   │   ├── setup_parsers.py  # AOT Tree-sitter parser builder
│   │   ├── parsers.py        # Multi-language AST loaders
│   │   ├── ast_auditor.py    # Determinism checks (Python, R, Julia, .ipynb)
│   │   ├── path_auditor.py   # Hardcoded path detection
│   │   ├── dependency_auditor.py              # Dependency analysis (Python, R, Julia)
│   │   ├── semantic_auditor.py                # LLM README audit
│   │   ├── import_graph.py                    # Cross-file import graph, cycle detection, flow tracing
│   │   ├── data_provenance_auditor.py         # Data loading, URL liveness, gated datasets
│   │   ├── hardware_fingerprinting_auditor.py # Anti-sandbox / Hardware identification
│   │   ├── configuration_drift_auditor.py     # Hyperparameter discrepancy detection
│   │   ├── auto_remediator.py                 # AST-powered deterministic code-mod engine
│   │   └── scoring.py                         # Weighted score computation
│   └── tests/
│       ├── test_ast_auditor.py
│       ├── test_path_auditor.py
│       ├── test_dependency_auditor.py
│       ├── test_import_graph.py
│       ├── test_auto_remediator.py 
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
│   │   ├── ScoreHistory.tsx  # Score trend line chart
│   │   ├── FixFeed.tsx       # Prioritized issue list
│   │   └── StatusIndicator.tsx   # Progress stepper
│   └── lib/
│       └── api.ts            # Typed API client
├── render.yaml               # Render Blueprint
├── action.yml                # GitHub Action metadata
├── action/
│   └── audit.py              # GitHub Action script (stdlib only)
├── .github/
│   └── workflows/
│       └── repoaudit.yml     # CI workflow for this repo
├── docker-compose.yml        # Local development
└── LICENSE
```

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 20+
- Valkey (local dev) or [Upstash](https://upstash.com) account (free tier, production)
- [Supabase](https://supabase.com) account (free tier)
- [Hugging Face](https://huggingface.co/settings/tokens) API key (free tier)

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

### Option A: Docker (local development)

```bash
# 1. Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env with your Supabase + Hugging Face keys

# 2. Start everything
docker compose up --build
```

Frontend at `http://localhost:3000`, API at `http://localhost:7860`.

### Option B: Local without Docker

```bash
# Backend
cd backend
cp .env.example .env
# Edit .env with your keys
pip install -r requirements.txt
valkey-server &
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

## Deployment

RepoAudit runs on an entirely free stack:

| Service | Platform | Cost |
|---------|----------|------|
| Backend (API + Celery) | [Render](https://render.com) | $0 |
| Frontend | [Vercel](https://vercel.com) | $0 |
| Redis (cache + broker) | [Upstash](https://upstash.com) | $0 |
| Database | [Supabase](https://supabase.com) | $0 |
| LLM | [Hugging Face](https://huggingface.co) | $0 |

### Deploy with Render Blueprint

1. **Upstash** — Create a Redis database at [console.upstash.com](https://console.upstash.com). Copy the `rediss://` URL.

2. **Render** — Go to [render.com](https://render.com) → **New** → **Blueprint** → connect this repo. Render auto-detects render.yaml and prompts for env vars:

   | Key | Value |
   |-----|-------|
   | `SUPABASE_URL` | Your Supabase project URL |
   | `SUPABASE_KEY` | Your Supabase anon key |
   | `HF_API_KEY` | Your Hugging Face API key |
   | `REDIS_URL` | `rediss://default:...@....upstash.io:6379` |
   | `CELERY_BROKER_URL` | Same Upstash URL |
   | `CELERY_RESULT_BACKEND` | Same Upstash URL |
   | `ALLOWED_ORIGINS` | `https://your-app.vercel.app,http://localhost:3000` |

3. **Vercel** — Import this repo → set **Root Directory** to frontend → add env var:

   | Key | Value |
   |-----|-------|
   | `NEXT_PUBLIC_API_URL` | `https://your-app.onrender.com` |

4. **Update ALLOWED_ORIGINS** on Render to include your Vercel URL.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/audit` | Submit a repo URL for analysis |
| `GET` | `/api/v1/audit/{id}` | Get full audit result |
| `GET` | `/api/v1/audit/{id}/status` | Poll task progress |
| `GET` | `/api/v1/audit/history/{owner}/{repo}` | Score history across audits |
| `GET` | `/health` | Health check |

**Example:**

```bash
curl -X POST https://repoaudit-api.onrender.com/api/v1/audit \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/owner/repo"}'
```

*Note: You can also submit research paper URLs (e.g., from arXiv, Papers With Code, NeurIPS) and RepoAudit will automatically resolve them to their corresponding GitHub repository.*

## How Caching Works

1. On submission, the API resolves the repo's latest `commit_hash` via `git ls-remote`
2. If that hash exists in Upstash Redis (L1) or Supabase Postgres (L2), the cached report is returned instantly
3. Otherwise, a Celery task clones the repo (depth=1) and runs the full analysis pipeline

## Features

- **Deterministic Auto-Remediation Engine**: Powered by offline AST manipulation, it instantly fixes high-confidence reproducibility blockers by injecting missing seeds, dynamically pinning unpinned dependencies, and rewriting hardcoded paths, outputting a concrete `.patch` file natively without LLMs.
- **Data Provenance Auditing**: Detects how data is loaded, checks URL liveness, flags gated datasets, and identifies non-deterministic preprocessing.
- **Configuration Drift Detection**: Catches discrepancies between claimed hyperparameters in README and actual values in config files or code defaults.
- **Reproducibility Scoring**: A weighted 0-100 score based on environment, determinism, datasets, and semantic alignment.

## Score History

When a repository is audited multiple times, RepoAudit tracks score progression over time. The audit detail page renders an interactive line chart showing:

- **Total score** trend across audits
- **Per-category breakdown** (togglable) for environment, determinism, datasets, semantic, execution, and documentation
- Commit hash labels on hover

```bash
curl https://repoaudit-api.onrender.com/api/v1/audit/history/owner/repo?limit=20
```

## GitHub Action

RepoAudit ships as a reusable GitHub Action.  

This repository self-tests the action with `uses: ./`, while external repositories should use `uses: sadhumitha-s/RepoAudit@v1.0.0`.

### Recommended usage (external repos)

```yaml
name: RepoAudit
on:
  pull_request:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: sadhumitha-s/RepoAudit@v1.0.0
        id: audit
        with:
          api-url: https://repoaudit-api.onrender.com
          threshold: "50"
          timeout-seconds: "600"
          poll-interval-seconds: "5"
          request-timeout-seconds: "180"
          request-retries: "4"
      - run: echo "Score — ${{ steps.audit.outputs.score }}/100"
```

### Action Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `api-url` | Yes | — | Base URL of your RepoAudit API |
| `repo-url` | No | Current repo | Override the repo URL to audit |
| `threshold` | No | `0` | Minimum score to pass the build |
| `timeout-seconds` | No | `600` | Max total wait for audit completion |
| `poll-interval-seconds` | No | `5` | Status poll interval |
| `request-timeout-seconds` | No | `180` | Per HTTP request timeout |
| `request-retries` | No | `4` | Retries for transient network/gateway failures |

### Action Outputs

| Output | Description |
|--------|-------------|
| `score` | Reproducibility score (0–100) |
| `audit-id` | Unique audit ID |
| `status` | `completed` or `failed` |
| `report-json` | Full report JSON |

### CI modes in this repository

The workflow in .github/workflows/repoaudit.yml includes:
- PR gate (`threshold: 50`)
- Manual strict+relaxed test matrix
- Monthly smoke run (`threshold: 0`)
