from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from enum import Enum
from datetime import datetime
import re

_GITHUB_URL_RE = re.compile(
    r"^https://github\.com/[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+/?$"
)


class AuditRequest(BaseModel):
    url: str = Field(..., description="Public GitHub repository URL")

    @field_validator("url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        if not _GITHUB_URL_RE.match(v + "/"):
            raise ValueError(
                "URL must be a valid public GitHub repository "
                "(e.g. https://github.com/owner/repo)"
            )
        return v


class AuditStatus(str, Enum):
    QUEUED = "queued"
    CLONING = "cloning"
    AST_ANALYSIS = "ast_analysis"
    SEMANTIC_AUDIT = "semantic_audit"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"


class Issue(BaseModel):
    rule: str
    severity: str = Field(..., pattern=r"^(critical|warning|info)$")
    file: str = ""
    line: int | None = None
    message: str
    fix: str = ""


class CategoryScore(BaseModel):
    name: str
    weight: float
    score: float = Field(ge=0, le=100)
    issues: list[Issue] = []


class AuditReport(BaseModel):
    categories: list[CategoryScore]
    total_score: float = Field(ge=0, le=100)
    summary: str = ""


class AuditResponse(BaseModel):
    audit_id: str
    repo_url: str
    status: AuditStatus
    commit_hash: str | None = None
    score: float | None = None
    report: AuditReport | None = None
    created_at: str | None = None
    cached: bool = False


class AuditStatusResponse(BaseModel):
    audit_id: str
    status: AuditStatus
    progress: str = ""


class ScoreHistoryPoint(BaseModel):
    audit_id: str
    commit_hash: str
    score: float = Field(ge=0, le=100)
    categories: list[CategoryScore] = []
    created_at: str


class ScoreHistoryResponse(BaseModel):
    owner: str
    repo: str
    points: list[ScoreHistoryPoint]