"""
Audit API endpoints.
"""

from __future__ import annotations
import json
import uuid
import logging

import redis as redis_lib
from fastapi import APIRouter, HTTPException, Query

from config import get_settings
from db import get_db
from engine.cloner import resolve_commit_hash
from models import (
    AuditRequest,
    AuditResponse,
    AuditStatus,
    AuditStatusResponse,
    AuditReport,
    CategoryScore,
    ScoreHistoryPoint,
    ScoreHistoryResponse,
)
from tasks import run_audit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["audit"])


def _get_redis() -> redis_lib.Redis:
    settings = get_settings()
    return redis_lib.from_url(settings.redis_url, decode_responses=True)


@router.post("/audit", response_model=AuditResponse)
async def submit_audit(req: AuditRequest):
    """Submit a repository for audit. Returns cached result or queues a new task."""
    url = req.url

    # Step 1: Resolve latest commit hash
    try:
        commit_hash = resolve_commit_hash(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Step 2: Check Redis cache
    try:
        r = _get_redis()
        cached = r.get(f"audit:result:{commit_hash}")
        if cached:
            data = json.loads(cached)
            return AuditResponse(
                audit_id=data["audit_id"],
                repo_url=url,
                status=AuditStatus.COMPLETED,
                commit_hash=commit_hash,
                score=data["score"],
                report=AuditReport(**data["report"]),
                cached=True,
            )
    except redis_lib.RedisError as e:
        logger.warning("Redis cache check failed: %s", e)

    # Step 3: Check database for existing result
    try:
        db = get_db()
        existing = (
            db.table("audits")
            .select("id, score, report_json, created_at")
            .eq("commit_hash", commit_hash)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if existing.data:
            row = existing.data[0]
            report_data = row["report_json"]
            if isinstance(report_data, str):
                report_data = json.loads(report_data)

            if "error" not in report_data:
                return AuditResponse(
                    audit_id=row["id"],
                    repo_url=url,
                    status=AuditStatus.COMPLETED,
                    commit_hash=commit_hash,
                    score=row["score"],
                    report=AuditReport(**report_data),
                    created_at=row.get("created_at"),
                    cached=True,
                )
    except Exception as e:
        logger.warning("Database cache check failed: %s", e)

    # Step 4: Queue new audit
    audit_id = str(uuid.uuid4())
    run_audit.delay(audit_id, url, commit_hash)

    # Set initial status
    try:
        r = _get_redis()
        r.set(f"audit:status:{audit_id}", AuditStatus.QUEUED.value, ex=3600)
    except redis_lib.RedisError:
        pass

    return AuditResponse(
        audit_id=audit_id,
        repo_url=url,
        status=AuditStatus.QUEUED,
        commit_hash=commit_hash,
    )


@router.get("/audit/history/{owner}/{repo}", response_model=ScoreHistoryResponse)
async def get_score_history(
    owner: str,
    repo: str,
    limit: int = Query(default=50, ge=1, le=200),
):
    """Get score history for a repository across audits."""
    db = get_db()

    # Find the repository
    repo_result = (
        db.table("repositories")
        .select("id")
        .eq("owner", owner)
        .eq("name", repo)
        .limit(1)
        .execute()
    )

    if not repo_result.data:
        raise HTTPException(status_code=404, detail="Repository not found")

    repo_id = repo_result.data[0]["id"]

    # Fetch audits chronologically
    audits = (
        db.table("audits")
        .select("id, commit_hash, score, report_json, created_at")
        .eq("repo_id", repo_id)
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    )

    points: list[ScoreHistoryPoint] = []
    for row in audits.data:
        report_data = row["report_json"]
        if isinstance(report_data, str):
            report_data = json.loads(report_data)

        # Skip failed audits
        if "error" in report_data:
            continue

        categories = [
            CategoryScore(
                name=cat["name"],
                weight=cat["weight"],
                score=cat["score"],
                issues=[],  # Omit issues for brevity
            )
            for cat in report_data.get("categories", [])
        ]

        points.append(
            ScoreHistoryPoint(
                audit_id=row["id"],
                commit_hash=row["commit_hash"],
                score=row["score"],
                categories=categories,
                created_at=row["created_at"],
            )
        )

    return ScoreHistoryResponse(owner=owner, repo=repo, points=points)


@router.get("/audit/{audit_id}", response_model=AuditResponse)
async def get_audit(audit_id: str):
    """Get audit result by ID."""
    # Validate UUID format
    try:
        uuid.UUID(audit_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid audit ID format")

    # Check database
    try:
        db = get_db()
        result = (
            db.table("audits")
            .select("id, commit_hash, score, report_json, created_at, repo_id")
            .eq("id", audit_id)
            .limit(1)
            .execute()
        )

        if result.data:
            row = result.data[0]
            report_data = row["report_json"]
            if isinstance(report_data, str):
                report_data = json.loads(report_data)

            # Get repo URL
            repo_url = ""
            if row.get("repo_id"):
                repo_resp = (
                    db.table("repositories")
                    .select("url")
                    .eq("id", row["repo_id"])
                    .limit(1)
                    .execute()
                )
                if repo_resp.data:
                    repo_url = repo_resp.data[0]["url"]

            if "error" in report_data:
                return AuditResponse(
                    audit_id=audit_id,
                    repo_url=repo_url,
                    status=AuditStatus.FAILED,
                    commit_hash=row["commit_hash"],
                    score=0,
                    created_at=row.get("created_at"),
                )

            return AuditResponse(
                audit_id=audit_id,
                repo_url=repo_url,
                status=AuditStatus.COMPLETED,
                commit_hash=row["commit_hash"],
                score=row["score"],
                report=AuditReport(**report_data),
                created_at=row.get("created_at"),
            )
    except Exception as e:
        logger.error("Database query failed: %s", e)

    # Check if task is still running
    try:
        r = _get_redis()
        status = r.get(f"audit:status:{audit_id}")
        if status:
            return AuditResponse(
                audit_id=audit_id,
                repo_url="",
                status=AuditStatus(status),
            )
    except redis_lib.RedisError:
        pass

    raise HTTPException(status_code=404, detail="Audit not found")


@router.get("/audit/{audit_id}/status", response_model=AuditStatusResponse)
async def get_audit_status(audit_id: str):
    """Get current status of an audit (lightweight polling endpoint)."""
    try:
        uuid.UUID(audit_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid audit ID format")

    # Check Redis first (fastest)
    try:
        r = _get_redis()
        status = r.get(f"audit:status:{audit_id}")
        if status:
            return AuditStatusResponse(
                audit_id=audit_id,
                status=AuditStatus(status),
                progress=_status_to_progress(AuditStatus(status)),
            )
    except redis_lib.RedisError:
        pass

    # Fallback: check database
    try:
        db = get_db()
        result = (
            db.table("audits")
            .select("id")
            .eq("id", audit_id)
            .limit(1)
            .execute()
        )
        if result.data:
            return AuditStatusResponse(
                audit_id=audit_id,
                status=AuditStatus.COMPLETED,
                progress="Analysis complete",
            )
    except Exception:
        pass

    raise HTTPException(status_code=404, detail="Audit not found")


def _status_to_progress(status: AuditStatus) -> str:
    return {
        AuditStatus.QUEUED: "Waiting in queue...",
        AuditStatus.CLONING: "Cloning repository...",
        AuditStatus.AST_ANALYSIS: "Running static analysis...",
        AuditStatus.SEMANTIC_AUDIT: "Performing semantic audit...",
        AuditStatus.FINALIZING: "Computing scores...",
        AuditStatus.COMPLETED: "Analysis complete",
        AuditStatus.FAILED: "Analysis failed",
    }.get(status, "Processing...")