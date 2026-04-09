# RepoAudit

Automated reproducibility analysis for machine learning research repositories (supporting Python, R, Julia, and Jupyter Notebooks) using AST-based static analysis and LLM-powered semantic auditing.

[![CI](https://github.com/sadhumitha-s/RepoAudit/actions/workflows/repoaudit.yml/badge.svg?label=CI)](https://github.com/sadhumitha-s/RepoAudit/actions/workflows/repoaudit.yml) 
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE) 
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/) 
[![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js&logoColor=white)](https://nextjs.org/) 
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/) 
[![GitHub stars](https://img.shields.io/github/stars/sadhumitha-s/RepoAudit?style=social)](https://github.com/sadhumitha-s/RepoAudit/stargazers)

**Live:** [repo-audit.vercel.app](https://repo-audit.vercel.app) · **API:** [repoaudit-api.onrender.com](https://repoaudit-api.onrender.com/health)

Watch the [Demo video](https://www.youtube.com/watch?v=sXdnrQQye8I)

## Table of Contents

- [What It Does](#what-it-does)
- [What's New in v2.0](#whats-new-in-v20)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Deployment](#deployment)
- [API Endpoints](#api-endpoints)
- [Features](#features)
- [GitHub Action](#github-action)
- [Documentation](#documentation)

## What It Does

RepoAudit scans public GitHub ML repositories and produces a **reproducibility score (0–100)** across six categories:

| Category | Weight | Checks |
|-------|-----------| ------- |
| Environment | 15% | Pinned dependencies, Dockerfile, **Reproducibility Decay Tracking** (Yanked pkgs, CVEs, shelf-life) |
| Determinism | 20% | AST-verified seeding, **Non-deterministic shuffling detection**, Notebook out-of-order execution, cell mutation |
| Datasets | 15% | No hardcoded paths, **Data Provenance (URL liveness, gated datasets)** |
| Semantic | 20% | AI-verified alignment between README and repo structure |
| Execution | 20% | **L0–L3 Replay Verification via Bubblewrap**, Presence of standard entry points (`train.py`, `Makefile`, etc.) |
| Documentation | 10% | README sections for Installation, Usage, Datasets |

## What's New in v2.0

- **Multi-Repository Comparative Analysis**: Benchmark up to 5 repositories side-by-side with overlaid radar charts and **"Golden Standard"** identification.
- **Reproducibility Decay Tracking**: Monitor "bit rot" via dependency stale-dating, yanked package detection, and CVE scanning with temporal decay curves.
- **Execution Replay Verification**: Lightweight **Bubblewrap sandboxing** for L0–L3 dynamic reproduction checks (Deps -> Imports -> Entrypoints -> Outputs).
- **Notebook Deep Analysis**: Advanced AST auditing for Jupyter Notebooks (out-of-order execution, global state mutation detection, and "Restart & Run All" compatibility).
- **Automated GitHub Release Workflow**: Streamlined versioning and deployment via GitHub Actions.
- **Optimized Audit Engine**: Faster analysis with non-essential directory skipping and robust Celery task management.

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
│   │   ├── notebook_analyzer.py   # Deep analysis for Jupyter Notebooks
│   │   ├── path_auditor.py   # Hardcoded path detection
│   │   ├── dependency_auditor.py              # Dependency analysis (Python, R, Julia)
│   │   ├── semantic_auditor.py                # LLM README audit
│   │   ├── import_graph.py                    # Cross-file import graph, cycle detection, flow tracing
│   │   ├── data_provenance_auditor.py         # Data loading, URL liveness, gated datasets
│   │   ├── hardware_fingerprinting_auditor.py # Anti-sandbox / Hardware identification
│   │   ├── configuration_drift_auditor.py     # Hyperparameter discrepancy detection
│   │   ├── sandbox.py                         # Bubblewrap orchestration
│   │   ├── replay_auditor.py                  # Dynamic L0–L3 execution verification
│   │   ├── decay_auditor.py                   # Reproducibility decay (bit rot) tracking
│   │   ├── auto_remediator.py                 # AST-powered deterministic code-mod engine
│   │   └── scoring.py                         # Weighted score computation
│   └── tests/
│       ├── test_ast_auditor.py
│       ├── test_path_auditor.py
│       ├── test_dependency_auditor.py
│       ├── test_import_graph.py
│       ├── test_replay_auditor.py
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
│   │   ├── DecayCard.tsx     # Decay curve & shelf-life visualization
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
| `POST` | `/api/v1/compare` | Compare up to 5 repo URLs |
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
- **Notebook-Specific Deep Analysis**: Goes beyond basic extraction to detect out-of-order cell execution (variable used before definition in earlier cells), identifies global state mutations (top-level assignments/imports), verifies "Restart and Run All" compatibility, and flags non-reproducible runtime dependency installations (e.g., `!pip install`).
- **Execution Replay Verification (Lightweight)**: Goes beyond static analysis by performing a 4-tier reproduction check in a **Bubblewrap sandbox** (L0: Deps Install, L1: Import Success, L2: Entry point runs for >5s, L3: Output Production), providing a pass/fail signal for the actual reproducibility of the claimed workflow.
- **Reproducibility Decay Tracking**: Quantifies "bit rot" by performing temporal analysis on pinned dependencies. It integrates with PyPI/CRAN/Pkg registries to detect yanked distributions and known CVEs, generating a predicted "shelf-life" score and decay curve visualization for long-term auditability.
- **Reproducibility Scoring**: A weighted 0-100 score based on environment, determinism, datasets, and semantic alignment.
- **Multi-Repository Comparative Analysis**: Compare reproducibility across related repositories (e.g., competing implementations of the same paper). Features an overlaid radar chart for 6-axis category breakdown, identifies the "Golden Standard" implementation with a 0-100 benchmark, and provides a unified comparison dashboard for research reviewers and reproducibility chairs.

## GitHub Action

RepoAudit can be integrated into your CI/CD pipeline to automatically audit PRs.

```yaml
      - uses: sadhumitha-s/RepoAudit@v2.0.0
        with:
          api-url: https://repoaudit-api.onrender.com
          threshold: "70"
```


## Documentation

- [**System Architecture**](docs/architecture.md) - Detailed architecture and component interaction.
- [**Scoring Methodology**](docs/scoring-methodology.md) - Deep dive into how reproducibility scores are calculated.
- [**API Reference**](docs/api-reference.md) - Comprehensive guide for all API endpoints.
- [**Development Guide**](docs/development-guide.md) - Setup for local development and contributing.
- [**GitHub Action Usage**](docs/github-action-usage.md) - Advanced configuration for the CI action.
- [**Comparison Guide**](docs/comparative-analysis.md) - Comparative analysis of multiple repositories.
- [**Contribution Guide**](docs/contribution.md) - Guidelines for contributing to the project.
