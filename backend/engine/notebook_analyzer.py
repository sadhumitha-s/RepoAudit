"""Notebook deep analysis utilities.
Provides functions to detect ordering issues, global state mutations, and runtime
dependency installations in Jupyter notebooks.
"""
import json
import ast
from pathlib import Path
from typing import List, Set, Tuple

from models import Issue


def _extract_cells(filepath: str) -> List[dict]:
    """Load notebook and return list of code cell dicts preserving order."""
    with open(filepath, "r", encoding="utf-8") as f:
        nb = json.load(f)
    return [c for c in nb.get("cells", []) if c.get("cell_type") == "code"]


def _parse_ast(source: str) -> ast.Module:
    return ast.parse(source)


def _collect_defs_uses(node: ast.AST) -> Tuple[Set[str], Set[str]]:
    """Return (defs, uses) sets of variable names defined and used in the AST.
    Assignments, function/class definitions count as defs. Name nodes in Load
    context count as uses.
    """
    defs: Set[str] = set()
    uses: Set[str] = set()

    class Visitor(ast.NodeVisitor):
        def visit_Name(self, node: ast.Name):
            if isinstance(node.ctx, ast.Store):
                defs.add(node.id)
            elif isinstance(node.ctx, ast.Load):
                uses.add(node.id)
        def visit_FunctionDef(self, node: ast.FunctionDef):
            defs.add(node.name)
            self.generic_visit(node)
        def visit_ClassDef(self, node: ast.ClassDef):
            defs.add(node.name)
            self.generic_visit(node)
        def visit_Import(self, node: ast.Import):
            for alias in node.names:
                defs.add(alias.asname or alias.name.split(".")[0])
        def visit_ImportFrom(self, node: ast.ImportFrom):
            for alias in node.names:
                defs.add(alias.asname or alias.name)

    Visitor().visit(node)
    return defs, uses


def analyze_notebook(filepath: str) -> List[Issue]:
    """Perform deep analysis on a notebook.
    Returns a list of `Issue` objects describing problems.
    """
    issues: List[Issue] = []
    cells = _extract_cells(filepath)
    defined: Set[str] = set()
    for idx, cell in enumerate(cells):
        source = "".join(cell.get("source", []))
        # Detect runtime dependency installation commands
        if "!pip install" in source or "!conda install" in source:
            issues.append(
                Issue(
                    rule="notebook_dependency",
                    severity="warning",
                    file=Path(filepath).name,
                    line=cell.get("metadata", {}).get("line_number", 1),
                    message="Runtime dependency installation detected; notebook may not be reproducible.",
                )
            )
        # Parse AST for defs/uses
        try:
            tree = _parse_ast(source)
        except SyntaxError:
            continue
        defs, uses = _collect_defs_uses(tree)
        # Out‑of‑order detection: use before definition
        for name in uses:
            if name not in defined:
                # Look ahead to see if defined later
                later_defined = any(
                    name in _collect_defs_uses(_parse_ast("".join(c.get("source", []))))[0]
                    for c in cells[idx + 1 :]
                )
                if later_defined:
                    issues.append(
                        Issue(
                            rule="notebook_order",
                            severity="warning",
                            file=Path(filepath).name,
                            line=cell.get("metadata", {}).get("line_number", 1),
                            message=f"Variable `{name}` used before definition (out‑of‑order execution).",
                        )
                    )
        # Global state mutation detection: any top‑level definition or import
        if defs:
            issues.append(
                Issue(
                    rule="notebook_global_mutation",
                    severity="info",
                    file=Path(filepath).name,
                    line=cell.get("metadata", {}).get("line_number", 1),
                    message="Cell mutates global notebook state (defines variables or imports).",
                )
            )
        defined.update(defs)
    return issues
