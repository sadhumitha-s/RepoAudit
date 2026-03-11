"""
Celery tasks for asynchronous repository auditing.
"""

from __future__ import annotations
import json
import logging
import redis as redis_lib

from worker import celery_app
from config import get_settings
from db import get_db
from engine import cloner, ast_auditor, path_auditor, dependency_auditor
from engine import semantic_auditor, scoring
from models import AuditStatus

logger = logging.getLogger(__name__)


def _get_redis() -> redis_lib.Redis:
    settings = get_settings()
    return redis_lib.from_url(settings.redis_url, decode_responses=True)


def _update_status(audit_id: str, status: AuditStatus) -> None:
    """Update audit status in Redis for real-time polling."""
    try:
        r = _get_redis()
        r.set(f"audit:status:{audit_id}", status.value, ex=3600)
    except Exception as e:
        logger.warning("Failed to update status in Redis: %s", e)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_audit(self, audit_id: str, repo_url: str, commit_hash: str) -> dict:
    """
    Main audit task. Clones repo, runs all analysis engines, stores results.
    """
    clone_path: str | None = None

    try:
        # Phase 1: Clone
        _update_status(audit_id, AuditStatus.CLONING)
        clone_path, owner, repo_name = cloner.clone_repo(repo_url)

        # Phase 2: AST Analysis
        _update_status(audit_id, AuditStatus.AST_ANALYSIS)
        _, det_issues = ast_auditor.audit_directory(clone_path)
        path_issues = path_auditor.audit_directory(clone_path)
        dep_result, dep_issues = dependency_auditor.audit_directory(clone_path)

        # Phase 3: Semantic Audit
        _update_status(audit_id, AuditStatus.SEMANTIC_AUDIT)
        sem_result, sem_issues = semantic_auditor.audit_directory(clone_path)

        # Phase 4: Scoring
        _update_status(audit_id, AuditStatus.FINALIZING)
        report = scoring.compute_report(
            repo_path=clone_path,
            det_issues=det_issues,
            path_issues=path_issues,
            dep_result=dep_result,
            dep_issues=dep_issues,
            semantic_result=sem_result,
            semantic_issues=sem_issues,
        )

        report_dict = report.model_dump()

        # Store in database
        db = get_db()

        # Upsert repository
        repo_resp = db.table("repositories").upsert(
            {"url": repo_url, "owner": owner, "name": repo_name},
            on_conflict="url",
        ).execute()

        repo_id = repo_resp.data[0]["id"]

        # Insert audit result
        db.table("audits").insert({
            "id": audit_id,
            "repo_id": repo_id,
            "commit_hash": commit_hash,
            "score": int(report.total_score),
            "report_json": report_dict,
        }).execute()

        # Cache in Redis
        try:
            r = _get_redis()
            cache_key = f"audit:result:{commit_hash}"
            r.set(cache_key, json.dumps({
                "audit_id": audit_id,
                "score": report.total_score,
                "report": report_dict,
            }), ex=86400)  # 24h cache
        except Exception as e:
            logger.warning("Failed to cache result in Redis: %s", e)

        _update_status(audit_id, AuditStatus.COMPLETED)

        return {
            "audit_id": audit_id,
            "score": report.total_score,
            "status": AuditStatus.COMPLETED.value,
        }

    except (ValueError, PermissionError) as e:
        # Non-retryable errors (bad URL, private repo, too large)
        logger.error("Audit %s failed (non-retryable): %s", audit_id, e)
        _update_status(audit_id, AuditStatus.FAILED)
        _store_failure(audit_id, repo_url, commit_hash, str(e))
        return {"audit_id": audit_id, "status": "failed", "error": str(e)}

    except Exception as e:
        logger.error("Audit %s failed: %s", audit_id, e, exc_info=True)
        _update_status(audit_id, AuditStatus.FAILED)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        _store_failure(audit_id, repo_url, commit_hash, str(e))
        return {"audit_id": audit_id, "status": "failed", "error": str(e)}

    finally:
        if clone_path:
            cloner.cleanup_clone(clone_path)


def _store_failure(
    audit_id: str, repo_url: str, commit_hash: str, error: str
) -> None:
    """Store a failed audit record in the database."""
    try:
        db = get_db()
        db.table("audits").upsert({
            "id": audit_id,
            "commit_hash": commit_hash,
            "score": 0,
            "report_json": {"error": error, "categories": [], "total_score": 0},
        }, on_conflict="id").execute()
    except Exception as e:
        logger.error("Failed to store failure record: %s", e)