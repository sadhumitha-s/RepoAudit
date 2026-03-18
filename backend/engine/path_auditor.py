"""
Hardcoded path detection.

Scans Python files for string literals that look like absolute local paths
(Windows, Linux, macOS home dirs) and flags them as non-portable.
"""

from __future__ import annotations
import ast
import os
import re
import logging
from dataclasses import dataclass

from models import Issue
from engine.parsers import extract_python_from_ipynb

logger = logging.getLogger(__name__)

# Patterns that indicate hardcoded local paths
_PATH_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Windows user path", re.compile(r"[A-Za-z]:\\Users\\", re.IGNORECASE)),
    ("Windows path", re.compile(r"[A-Za-z]:\\[A-Za-z]", re.IGNORECASE)),
    ("Linux home path", re.compile(r"/home/[a-zA-Z]")),
    ("macOS user path", re.compile(r"/Users/[a-zA-Z]")),
    ("Documents path", re.compile(r"[/\\]Documents[/\\]")),
    ("Desktop path", re.compile(r"[/\\]Desktop[/\\]")),
    ("Downloads path", re.compile(r"[/\\]Downloads[/\\]")),
    ("Temp path", re.compile(r"[A-Za-z]:\\[Tt]emp\\")),
]

# Allowlist: patterns that are acceptable (e.g., documentation, comments)
_ALLOW_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^https?://"),       # URLs
    re.compile(r"^ftp://"),
    re.compile(r"^ssh://"),
    re.compile(r"^git@"),
    re.compile(r"/usr/(bin|lib|local|share)/"),  # System paths (often valid)
    re.compile(r"/etc/"),
    re.compile(r"/dev/(null|zero|random)"),
]


@dataclass
class PathMatch:
    line: int
    value: str
    pattern_name: str


class _StringVisitor(ast.NodeVisitor):
    """Extract all string constants and f-string components from AST."""

    def __init__(self) -> None:
        self.strings: list[tuple[int, str]] = []

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and len(node.value) > 3:
            self.strings.append((node.lineno, node.value))
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        # f-strings: check the constant parts
        for val in node.values:
            if isinstance(val, ast.Constant) and isinstance(val.value, str):
                if len(val.value) > 3:
                    self.strings.append((node.lineno, val.value))
        self.generic_visit(node)


def _is_allowed(value: str) -> bool:
    return any(p.search(value) for p in _ALLOW_PATTERNS)


def audit_file(filepath: str) -> list[PathMatch]:
    """Scan a single Python file for hardcoded paths."""
    if filepath.endswith(".ipynb"):
        source = extract_python_from_ipynb(filepath)
    else:
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
        except OSError:
            return []

    if not source.strip():
        return []

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError:
        # Fallback: regex scan on raw source for non-parseable files
        return _regex_scan(source)

    visitor = _StringVisitor()
    visitor.visit(tree)

    matches: list[PathMatch] = []
    seen: set[tuple[int, str]] = set()

    for lineno, value in visitor.strings:
        if _is_allowed(value):
            continue
        for pattern_name, pattern in _PATH_PATTERNS:
            if pattern.search(value):
                key = (lineno, pattern_name)
                if key not in seen:
                    seen.add(key)
                    # Truncate long paths for readability
                    display = value if len(value) <= 80 else value[:77] + "..."
                    matches.append(PathMatch(
                        line=lineno, value=display, pattern_name=pattern_name
                    ))
                break  # One match per string per line is enough

    return matches


def _regex_scan(source: str) -> list[PathMatch]:
    """Fallback regex scan for files that can't be parsed as AST."""
    matches: list[PathMatch] = []
    for i, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for pattern_name, pattern in _PATH_PATTERNS:
            if pattern.search(line):
                matches.append(PathMatch(
                    line=i,
                    value=stripped[:80],
                    pattern_name=pattern_name,
                ))
                break
    return matches


def audit_directory(repo_path: str) -> list[Issue]:
    """Scan all Python files in a repo for hardcoded paths."""
    issues: list[Issue] = []

    for dirpath, dirnames, filenames in os.walk(repo_path):
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".")
            and d not in ("venv", ".venv", "env", "node_modules", "__pycache__")
        ]
        for fname in filenames:
            if not fname.endswith((".py", ".ipynb", ".r", ".jl")):
                continue
            fpath = os.path.join(dirpath, fname)
            rel = os.path.relpath(fpath, repo_path)
            matches = audit_file(fpath)

            for m in matches:
                issues.append(Issue(
                    rule="hardcoded_path",
                    severity="warning",
                    file=rel,
                    line=m.line,
                    message=(
                        f"Hardcoded {m.pattern_name} detected: `{m.value}`"
                    ),
                    fix=(
                        "Use `os.path.join()`, `pathlib.Path`, or environment "
                        "variables instead of absolute paths to ensure portability."
                    ),
                ))

    return issues