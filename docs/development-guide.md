# Development Guide

Welcome to the RepoAudit development guide! This document outlines how to set up your local environment, run tests, and contribute new features or auditors.

## 1. Local Environment Setup

RepoAudit requires a distributed environment for both its API and background workers. You have two options for local development:

### Option A: Docker (Recommended)
This is the easiest way to get everything running in a simulated production environment.

1.  **Configure `.env`**:
    ```bash
    cp backend/.env.example backend/.env
    # Edit .env with your local or Upstash/Supabase keys
    ```
2.  **Start Services**:
    ```bash
    docker compose up --build
    ```
    - **Frontend**: http://localhost:3000
    - **API**: http://localhost:7860
    - **Worker**: Logs will appear in the terminal.

### Option B: Local Manual Setup
Best for active development where you want faster reload times.

1.  **Install Dependencies**:
    - **Backend**: `cd backend && pip install -r requirements.txt`
    - **Frontend**: `cd frontend && npm install`
2.  **Start External Services**:
    - Ensure `valkey-server` (or `redis-server`) is running on port 6379.
3.  **Run Components**:
    - **Worker**: `celery -A worker worker --loglevel=info`
    - **API**: `uvicorn main:app --reload --port 7860`
    - **Frontend**: `npm run dev` (inside `frontend/`)

## 2. Project Structure Overview

- `backend/`: FastAPI application and Celery worker.
  - `engine/`: The core audit logic. Each auditor is a specialized module.
  - `routers/`: API endpoint definitions.
- `frontend/`: Next.js 15 application.
  - `app/`: App router pages.
  - `components/`: UI components (radar charts, score cards).

## 3. Adding a New Auditor

To extend RepoAudit with a new reproducibility check:

1.  **Create Auditor Module**: Add a new file in `backend/engine/` (e.g., `new_feature_auditor.py`).
2.  **Define Audit Function**: Implement the logic to scan the cloned repository path.
3.  **Regenerate Report**: Update `backend/engine/scoring.py` to include your new auditor and calculate how its results affect the category scores.
4.  **Update Models**: If your auditor returns new types of issues or metadata, update `backend/models.py`.

### Example Auditor Template:
```python
def audit_repo(repo_path: str) -> list[Issue]:
    issues = []
    # Core logic here...
    return issues
```

## 4. Testing Strategy

RepoAudit uses `pytest` for backend testing. We prioritize unit tests for individual auditors and integration tests for the scoring logic.

**Run All Tests**:
```bash
cd backend
pytest
```

**Run Specific Audit Tests**:
```bash
pytest tests/test_ast_auditor.py
```

## 5. Coding Standards

- **Python**: Follow PEP 8. Use type hints for all function signatures.
- **Frontend**: Use TypeScript for all components. Prefer functional components with React Hooks.
- **Commits**: Use descriptive commit messages.

---

[← Back to Main README](../readme.md)
