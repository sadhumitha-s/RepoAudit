# API Reference

The RepoAudit API is a RESTful service built with FastAPI. It provides endpoints to submit repositories for analysis, track audit status, and retrieve detailed reproducibility reports.

**Base URL:** `https://repoaudit-api.onrender.com` (Production)

---

## 1. Authentication
The current public API does not require authentication for basic auditing. However, rate limits may apply to prevent abuse.

---

## 2. Audit Endpoints

### `POST /api/v1/audit`
Submit a repository for audit. If the exact commit hash has already been audited, it returns the cached result instantly.

**Request Body:**
```json
{
  "url": "https://github.com/owner/repo"
}
```
*Note: You can also submit research paper URLs (e.g., from arXiv, Papers With Code, NeurIPS) and the API will automatically resolve them to their primary GitHub repository.*

**Response (New Audit):**
```json
{
  "audit_id": "uuid-v4-string",
  "repo_url": "https://github.com/owner/repo",
  "status": "queued",
  "commit_hash": "abc1234...",
  "cached": false
}
```

**Response (Cached Result):**
```json
{
  "audit_id": "uuid-v4-string",
  "repo_url": "https://github.com/owner/repo",
  "status": "completed",
  "commit_hash": "abc1234...",
  "score": 85,
  "report": { 
    "categories": [...],
    "decay_metrics": {
      "shelf_life_days": 1200,
      "time_to_break_days": 800,
      "decay_curve": [{"date": "Year -1", "score": 95.0}, ...]
    }
  },
  "cached": true
}
```

---

### `GET /api/v1/audit/{audit_id}`
Retrieve the full report for a specific audit.

**Response:**
Returns the `AuditResponse` object containing the score and detailed category breakdown.

---

### `GET /api/v1/audit/{audit_id}/status`
A lightweight endpoint for polling the progress of an active audit task.

**Response:**
```json
{
  "audit_id": "uuid-v4-string",
  "status": "ast_analysis",
  "progress": "Running static analysis..."
}
```

**Status Values:**
- `queued`: Waiting for an available worker.
- `cloning`: Repository is being shallow-cloned.
- `ast_analysis`: Running AST and dependency checks.
- `decay_analysis`: Analyzing dependency history (PyPI) for yanked packages and CVEs.
- `semantic_audit`: Performing LLM-powered README analysis.
- `finalizing`: Computing final scores and storing results.
- `completed`: Analysis finished successfully.
- `failed`: An error occurred during processing.

---

## 3. History Endpoints

### `GET /api/v1/audit/history/{owner}/{repo}`
Retrieve the score progression for a repository over time.

**Parameters:**
- `owner`: GitHub owner/org name.
- `repo`: Repository name.
- `limit`: (Optional) Max number of results (Default: 50, Max: 200).

**Response:**
```json
{
  "owner": "owner",
  "repo": "repo",
  "points": [
    {
      "audit_id": "uuid",
      "commit_hash": "...",
      "score": 75,
      "categories": [ ... ],
      "created_at": "..."
    },
    ...
  ]
}
```

---

## 4. Utility Endpoints

### `GET /health`
Returns the operational status of the API and its connection to backends (Redis, Database).

**Response:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "services": {
    "redis": "connected",
    "database": "connected"
  }
}
```

---

[← Back to Main README](../readme.md)
