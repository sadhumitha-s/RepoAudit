"""
Common utility functions for RepoAudit engine.
"""

from __future__ import annotations
import os

# Standard set of directories to ignore during repository audits to improve performance
# and focus on core source code.
IGNORED_DIRS = {
    "venv",
    ".venv",
    "env",
    ".env",
    "node_modules",
    "__pycache__",
    ".git",
    ".github",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    ".nox",
    "build",
    "dist",
    "docs",
    "examples",
    "tests",
    "test",
    "benchmarks",
    "samples",
    "vendor",
    "out",
    "bin",
    "obj",
}


def skip_ignored_dirs(dirnames: list[str]) -> None:
    """
    In-place modification of dirnames for use with os.walk to skip ignored directories.
    
    Example:
        for dirpath, dirnames, filenames in os.walk(repo_path):
            skip_ignored_dirs(dirnames)
            ...
    """
    dirnames[:] = [d for d in dirnames if d.lower() not in IGNORED_DIRS and not d.startswith(".")]


def resolve_call_name(node: ast.Call) -> str | None:
    """Resolve a call node to a dotted string like 'torch.manual_seed'."""
    import ast
    parts: list[str] = []
    current = node.func
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    else:
        return None
    return ".".join(reversed(parts))
