"""
Scoring engine.

Computes a weighted reproducibility score from 0–100 based on
6 audit categories, now enhanced with cross-file flow analysis.
"""

from __future__ import annotations
import os

from models import CategoryScore, AuditReport, Issue
from engine.dependency_auditor import DependencyAuditResult
from engine.semantic_auditor import SemanticAuditResult


CATEGORY_WEIGHTS: dict[str, float] = {
    "environment": 0.20,
    "determinism": 0.20,
    "datasets": 0.20,
    "semantic": 0.20,
    "execution": 0.10,
    "documentation": 0.10,
}


def _score_environment(
    dep_result: DependencyAuditResult,
    env_issues: list[Issue],
) -> CategoryScore:
    """Score environment reproducibility (requirements, pinning)."""
    score = 100.0

    if not (
        dep_result.has_requirements_txt
        or dep_result.has_environment_yml
        or dep_result.has_pyproject_toml
        or dep_result.has_setup_py
        or dep_result.has_r_description
        or dep_result.has_r_renv
        or dep_result.has_julia_project
    ):
        score -= 60

    if dep_result.has_dockerfile:
        score = min(score + 10, 100)

    if dep_result.total_deps > 0:
        pin_ratio = dep_result.pinned_count / dep_result.total_deps
        score -= (1 - pin_ratio) * 30
    elif dep_result.has_requirements_txt:
        score -= 20

    if dep_result.missing_deps:
        penalty = min(len(dep_result.missing_deps) * 5, 20)
        score -= penalty

    score = max(0, min(100, score))
    return CategoryScore(
        name="environment",
        weight=CATEGORY_WEIGHTS["environment"],
        score=round(score, 1),
        issues=[i for i in env_issues if i.rule == "dependency"],
    )


def _score_determinism(
    det_issues: list[Issue],
    graph_issues: list[Issue],
) -> CategoryScore:
    """Score determinism based on AST audit + cross-file flow analysis."""
    score = 100.0

    all_issues = [i for i in det_issues if i.rule == "determinism"]
    # Add flow-based determinism issues (avoid duplicates by checking message)
    seen_messages: set[str] = {i.message for i in all_issues}
    for i in graph_issues:
        if i.rule == "determinism" and i.message not in seen_messages:
            all_issues.append(i)
            seen_messages.add(i.message)

    critical = sum(1 for i in all_issues if i.severity == "critical")
    warnings = sum(1 for i in all_issues if i.severity == "warning")

    score -= critical * 40
    score -= warnings * 10

    score = max(0, min(100, score))
    return CategoryScore(
        name="determinism",
        weight=CATEGORY_WEIGHTS["determinism"],
        score=round(score, 1),
        issues=all_issues,
    )


def _score_datasets(
    path_issues: list[Issue],
    semantic_result: SemanticAuditResult,
) -> CategoryScore:
    """Score dataset handling (hardcoded paths, data documentation)."""
    score = 100.0
    issues: list[Issue] = []

    path_count = len(path_issues)
    score -= min(path_count * 10, 50)
    issues.extend(path_issues)

    if semantic_result.missing_data_dirs:
        score -= len(semantic_result.missing_data_dirs) * 15

    score = max(0, min(100, score))
    return CategoryScore(
        name="datasets",
        weight=CATEGORY_WEIGHTS["datasets"],
        score=round(score, 1),
        issues=issues,
    )


def _score_semantic(
    semantic_result: SemanticAuditResult,
    semantic_issues: list[Issue],
) -> CategoryScore:
    """Score semantic alignment between README and code."""
    score = 100.0

    if not semantic_result.has_readme:
        score = 0
    else:
        missing_files = len(semantic_result.missing_files)
        score -= min(missing_files * 15, 60)

        if semantic_result.llm_error:
            score = max(score, 50)

    score = max(0, min(100, score))
    return CategoryScore(
        name="semantic",
        weight=CATEGORY_WEIGHTS["semantic"],
        score=round(score, 1),
        issues=[i for i in semantic_issues if i.rule == "semantic"],
    )


def _score_execution(
    repo_path: str,
    graph_issues: list[Issue],
) -> CategoryScore:
    """Score presence of entry points + execution flow health."""
    score = 0.0
    issues: list[Issue] = []

    entry_points = [
        "main.py", "train.py", "run.py", "app.py",
        "Makefile", "setup.py", "pyproject.toml",
    ]

    root_files = set()
    if os.path.isdir(repo_path):
        root_files = {f.lower() for f in os.listdir(repo_path)}

    found = [ep for ep in entry_points if ep.lower() in root_files]

    if found:
        score = min(len(found) * 35, 100)
    else:
        issues.append(Issue(
            rule="execution",
            severity="warning",
            message=(
                "No standard entry point found (main.py, train.py, Makefile, etc.)."
            ),
            fix="Add a main entry point like `train.py` or `main.py`.",
        ))

    # Penalize circular imports (affects execution reliability)
    circular = [i for i in graph_issues if i.rule == "circular_import"]
    score -= len(circular) * 15
    issues.extend(circular)

    # Penalize missing execution flow
    flow_issues = [i for i in graph_issues if i.rule == "execution_flow"]
    score -= len(flow_issues) * 10
    issues.extend(flow_issues)

    score = max(0, min(100, score))
    return CategoryScore(
        name="execution",
        weight=CATEGORY_WEIGHTS["execution"],
        score=round(score, 1),
        issues=issues,
    )


def _score_documentation(
    semantic_result: SemanticAuditResult,
    doc_issues: list[Issue],
) -> CategoryScore:
    """Score documentation quality."""
    score = 100.0

    if not semantic_result.has_readme:
        score = 0
    else:
        required = ["installation", "usage", "datasets"]
        present = sum(
            1 for s in required
            if semantic_result.sections_present.get(s, False)
        )
        if len(required) > 0:
            score = (present / len(required)) * 100

    score = max(0, min(100, score))
    return CategoryScore(
        name="documentation",
        weight=CATEGORY_WEIGHTS["documentation"],
        score=round(score, 1),
        issues=[i for i in doc_issues if i.rule == "documentation"],
    )


def compute_report(
    repo_path: str,
    det_issues: list[Issue],
    path_issues: list[Issue],
    dep_result: DependencyAuditResult,
    dep_issues: list[Issue],
    semantic_result: SemanticAuditResult,
    semantic_issues: list[Issue],
    graph_issues: list[Issue] | None = None,
) -> AuditReport:
    """Compute the full audit report with weighted scores."""
    if graph_issues is None:
        graph_issues = []

    categories = [
        _score_environment(dep_result, dep_issues),
        _score_determinism(det_issues, graph_issues),
        _score_datasets(path_issues, semantic_result),
        _score_semantic(semantic_result, semantic_issues),
        _score_execution(repo_path, graph_issues),
        _score_documentation(semantic_result, semantic_issues),
    ]

    total = sum(c.score * c.weight for c in categories)
    total = round(max(0, min(100, total)), 1)

    worst = min(categories, key=lambda c: c.score)
    if total >= 80:
        summary = "Repository has good reproducibility practices."
    elif total >= 50:
        summary = (
            f"Repository needs improvement. "
            f"Weakest area: {worst.name} ({worst.score}/100)."
        )
    else:
        summary = (
            f"Significant reproducibility concerns. "
            f"Critical area: {worst.name} ({worst.score}/100)."
        )

    return AuditReport(
        categories=categories,
        total_score=total,
        summary=summary,
    )