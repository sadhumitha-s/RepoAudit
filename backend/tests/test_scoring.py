import pytest
from models import Issue
from engine.scoring import compute_report, CATEGORY_WEIGHTS
from engine.dependency_auditor import DependencyAuditResult
from engine.semantic_auditor import SemanticAuditResult


class TestScoring:
    def test_perfect_score(self, tmp_repo, py_file):
        py_file("train.py", "")
        py_file("main.py", "")
        result = compute_report(
            repo_path=str(tmp_repo),
            det_issues=[],
            path_issues=[],
            dep_result=DependencyAuditResult(
                has_requirements_txt=True,
                pinned_count=5,
                total_deps=5,
            ),
            dep_issues=[],
            semantic_result=SemanticAuditResult(
                has_readme=True,
                sections_present={
                    "installation": True,
                    "usage": True,
                    "datasets": True,
                },
            ),
            semantic_issues=[],
        )
        assert result.total_score >= 80

    def test_zero_score(self, tmp_repo):
        result = compute_report(
            repo_path=str(tmp_repo),
            det_issues=[
                Issue(rule="determinism", severity="critical",
                      message="No seed found"),
            ],
            path_issues=[
                Issue(rule="hardcoded_path", severity="warning", file="a.py",
                      message="path", line=1)
                for _ in range(10)
            ],
            dep_result=DependencyAuditResult(),
            dep_issues=[
                Issue(rule="dependency", severity="critical",
                      message="No deps"),
            ],
            semantic_result=SemanticAuditResult(),
            semantic_issues=[
                Issue(rule="documentation", severity="critical",
                      message="No readme"),
            ],
        )
        assert result.total_score <= 30

    def test_score_bounded(self, tmp_repo):
        result = compute_report(
            repo_path=str(tmp_repo),
            det_issues=[],
            path_issues=[],
            dep_result=DependencyAuditResult(
                has_requirements_txt=True,
                has_dockerfile=True,
                pinned_count=10,
                total_deps=10,
            ),
            dep_issues=[],
            semantic_result=SemanticAuditResult(
                has_readme=True,
                sections_present={
                    "installation": True,
                    "usage": True,
                    "datasets": True,
                    "training": True,
                    "evaluation": True,
                },
            ),
            semantic_issues=[],
        )
        assert 0 <= result.total_score <= 100

    def test_weights_sum_to_one(self):
        total = sum(CATEGORY_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_report_has_all_categories(self, tmp_repo):
        result = compute_report(
            repo_path=str(tmp_repo),
            det_issues=[],
            path_issues=[],
            dep_result=DependencyAuditResult(),
            dep_issues=[],
            semantic_result=SemanticAuditResult(),
            semantic_issues=[],
        )
        names = {c.name for c in result.categories}
        assert names == set(CATEGORY_WEIGHTS.keys())