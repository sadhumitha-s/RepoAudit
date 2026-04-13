"""
Scoring engine.

Computes a weighted reproducibility score from 0–100 based on
6 audit categories, now enhanced with cross-file flow analysis.
"""

from __future__ import annotations
import os

from models import CategoryScore, AuditReport, Issue, DecayMetrics
from engine.dependency_auditor import DependencyAuditResult
from engine.semantic_auditor import SemanticAuditResult
from engine.replay_auditor import ExecutionReplayResult
from engine.decay_auditor import DecayAuditResult
from engine.pipeline_auditor import PipelineGraph


CATEGORY_WEIGHTS: dict[str, float] = {
    "environment": 0.15,
    "determinism": 0.20,
    "datasets": 0.15,
    "semantic": 0.20,
    "execution": 0.20,
    "documentation": 0.10,
}


def _score_environment(
    dep_result: DependencyAuditResult,
    env_issues: list[Issue],
    fingerprint_issues: list[Issue] | None = None,
    decay_result: DecayAuditResult | None = None,
    decay_issues: list[Issue] | None = None,
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

    # Penalize fingerprinting issues
    if fingerprint_issues:
        for fi in fingerprint_issues:
            if fi.severity == "critical":
                score -= 30
            elif fi.severity == "warning":
                score -= 10
            elif fi.severity == "info":
                score -= 2

    # Penalize decay issues
    if decay_result:
        score -= len(decay_result.yanked_packages) * 20
        score -= len(decay_result.cve_packages) * 10

    score = max(0, min(100, score))
    all_issues = [i for i in env_issues if i.rule == "dependency"]
    if decay_issues:
        all_issues.extend(decay_issues)
        
    return CategoryScore(
        name="environment",
        weight=CATEGORY_WEIGHTS["environment"],
        score=round(score, 1),
        issues=all_issues,
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
    provenance_issues: list[Issue],
) -> CategoryScore:
    """Score dataset handling (hardcoded paths, data documentation)."""
    score = 100.0
    issues: list[Issue] = []

    path_count = len(path_issues)
    score -= min(path_count * 10, 50)
    issues.extend(path_issues)

    if semantic_result.missing_data_dirs:
        score -= len(semantic_result.missing_data_dirs) * 15

    # Penalize provenance issues
    for pi in provenance_issues:
        if pi.severity == "critical":
            score -= 30
        elif pi.severity == "warning":
            score -= 15
        elif pi.severity == "info":
            score -= 5
        issues.append(pi)

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
    drift_issues: list[Issue] | None = None,
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

    # Penalize configuration drift
    if drift_issues:
        for di in drift_issues:
            if di.severity == "critical":
                score -= 20
            elif di.severity == "warning":
                score -= 10
            elif di.severity == "info":
                score -= 2

    all_semantic_issues = [i for i in semantic_issues if i.rule == "semantic"]
    if drift_issues:
        all_semantic_issues.extend(drift_issues)

    score = max(0, min(100, score))
    return CategoryScore(
        name="semantic",
        weight=CATEGORY_WEIGHTS["semantic"],
        score=round(score, 1),
        issues=all_semantic_issues,
    )


def _score_execution(
    repo_path: str,
    graph_issues: list[Issue],
    replay_result: ExecutionReplayResult | None = None,
    pipeline_graph: PipelineGraph | None = None,
) -> CategoryScore:
    """Score presence of entry points + dynamic execution replay verification."""
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

    # Dynamic Replay Score (Levels L0-L3)
    if replay_result and replay_result.highest_level >= 0:
        # L0: 25, L1: 50, L2: 80, L3: 100
        replay_scores = {0: 25, 1: 50, 2: 80, 3: 100}
        dynamic_score = replay_scores.get(replay_result.highest_level, 0)
        
        # Combine static entry-point discovery with dynamic results
        # If dynamic verification passed, it's a huge boost
        score = (score * 0.3) + (dynamic_score * 0.7)
    
    # Factor in Pipeline Completeness
    if pipeline_graph:
        # Completeness score contributes to the final execution score
        # 50% from static/dynamic entry points, 50% from pipeline completeness
        score = (score * 0.5) + (pipeline_graph.completeness_score * 0.5)
    elif replay_result and replay_result.error:
        # If it failed to even start (e.g. no bwrap), keep static score but add info
        pass

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
    provenance_issues: list[Issue] | None = None,
    fingerprint_issues: list[Issue] | None = None,
    drift_issues: list[Issue] | None = None,
    replay_result: ExecutionReplayResult | None = None,
    decay_result: DecayAuditResult | None = None,
    decay_issues: list[Issue] | None = None,
    pipeline_graph: PipelineGraph | None = None,
    pipeline_issues: list[Issue] | None = None,
) -> AuditReport:
    """Compute the full audit report with weighted scores."""
    if graph_issues is None:
        graph_issues = []
    if provenance_issues is None:
        provenance_issues = []

    categories = [
        _score_environment(dep_result, dep_issues, fingerprint_issues, decay_result, decay_issues),
        _score_determinism(det_issues, graph_issues),
        _score_datasets(path_issues, semantic_result, provenance_issues),
        _score_semantic(semantic_result, semantic_issues, drift_issues),
        _score_execution(repo_path, graph_issues, replay_result, pipeline_graph),
        _score_documentation(semantic_result, semantic_issues),
    ]

    all_issues = []
    if pipeline_issues:
        for cat in categories:
            if cat.name == "execution":
                cat.issues.extend(pipeline_issues)

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

    decay_metrics = None
    if decay_result:
        decay_metrics = DecayMetrics(
            shelf_life_days=decay_result.shelf_life_days,
            time_to_break_days=decay_result.time_to_break_days,
            decay_curve=decay_result.decay_curve
        )

    return AuditReport(
        categories=categories,
        total_score=total,
        summary=summary,
        decay_metrics=decay_metrics,
        pipeline_graph=pipeline_graph,
    )