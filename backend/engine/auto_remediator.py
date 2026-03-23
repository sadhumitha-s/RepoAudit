"""
Deterministic Auto-Remediation Engine
Applies AST-based and regex-based modifications to fix common reproducibility issues
and generates a unified diff patch.
"""

from __future__ import annotations
import os
import difflib
import logging
import httpx
from typing import Any

try:
    import libcst as cst
    import libcst.matchers as m
except ImportError:
    cst = None
    m = None

from models import Issue

logger = logging.getLogger(__name__)

# Cache for PyPI resolutions
_PYPI_CACHE: dict[str, str | None] = {}

def get_latest_pypi_version(package_name: str) -> str | None:
    """Fetch the latest version of a package from PyPI."""
    if package_name in _PYPI_CACHE:
        return _PYPI_CACHE[package_name]
    
    try:
        resp = httpx.get(f"https://pypi.org/pypi/{package_name}/json", timeout=5.0)
        if resp.status_code == 200:
            version = resp.json()["info"]["version"]
            _PYPI_CACHE[package_name] = version
            return version
    except Exception as e:
        logger.warning("Could not resolve version for %s: %s", package_name, e)
    
    _PYPI_CACHE[package_name] = None
    return None


class HardcodedPathTransformer(cst.CSTTransformer):
    """
    Finds hardcoded path strings (like /home/user/...) and attempts to 
    replace them with os.path.expanduser('~').
    """
    def __init__(self, target_line: int):
        self.target_line = target_line
        self.modified = False

    def leave_SimpleString(self, original_node: cst.SimpleString, updated_node: cst.SimpleString) -> cst.BaseExpression:
        # We can't perfectly map lines without PositionProvider, but we do a simpler approach:
        # If the string contains obvious hardcoded roots, replace it.
        val = original_node.value
        
        # Simplified rewriting for common paths
        val_clean = val.replace("\\\\", "\\")
        if "/home/" in val_clean or "C:\\Users\\" in val_clean or "/Users/" in val_clean:
            self.modified = True
            
            # e.g. "/home/user/data/data.csv" -> "~/data/data.csv"
            # Strip quotes
            inner = val[1:-1].replace("\\\\", "/")
            if "/home/" in inner:
                parts = inner.split("/home/", 1)[1].split("/", 1)
                new_inner = "~/" + (parts[1] if len(parts) > 1 else "")
            elif "C:/Users/" in inner:
                parts = inner.split("C:/Users/", 1)[1].split("/", 1)
                new_inner = "~/" + (parts[1] if len(parts) > 1 else "")
            elif "/Users/" in inner:
                parts = inner.split("/Users/", 1)[1].split("/", 1)
                new_inner = "~/" + (parts[1] if len(parts) > 1 else "")
            else:
                new_inner = "~/" # Fallback
                
            new_str = f'"{new_inner}"'
            
            # Return os.path.expanduser(new_str)
            return cst.Call(
                func=cst.Attribute(
                    value=cst.Attribute(value=cst.Name("os"), attr=cst.Name("path")),
                    attr=cst.Name("expanduser")
                ),
                args=[cst.Arg(value=cst.SimpleString(new_str))]
            )
            
        return updated_node

class InsertSeedTransformer(cst.CSTTransformer):
    """
    Injects `import torch` and `torch.manual_seed(42)` at the top of the file
    if random operations were detected but no seed is present.
    """
    def __init__(self):
        self.injected = False

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        if self.injected:
            return updated_node

        # We'll insert an import statement and a seed call at the top just after docstrings/imports
        # Create the AST nodes
        import_stmt = cst.SimpleStatementLine(body=[cst.Import(names=[cst.ImportAlias(name=cst.Name("torch"))])])
        seed_stmt = cst.SimpleStatementLine(body=[
            cst.Expr(
                value=cst.Call(
                    func=cst.Attribute(value=cst.Name("torch"), attr=cst.Name("manual_seed")),
                    args=[cst.Arg(value=cst.Integer("42"))]
                )
            )
        ])

        new_body = [import_stmt, seed_stmt] + list(updated_node.body)
        self.injected = True
        return updated_node.with_changes(body=tuple(new_body))


def fix_python_file(filepath: str, issues: list[Issue]) -> str | None:
    """Apply AST transformations to a Python file based on issues."""
    if not cst:
        return None
        
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
    except OSError:
        return None

    try:
        tree = cst.parse_module(source)
    except Exception:
        return None

    modified = False

    # Check which fixes are needed
    needs_seed = any(i.rule == "determinism" and "no reachable seed" in i.message.lower() for i in issues)
    path_issues = [i for i in issues if i.rule == "hardcoded_path"]

    if needs_seed:
        transformer = InsertSeedTransformer()
        tree = tree.visit(transformer)
        modified = True

    if path_issues:
        # Just run the HardcodedPathTransformer globally to fix strings
        transformer = HardcodedPathTransformer(target_line=0)
        tree = tree.visit(transformer)
        if transformer.modified:
            # We must ensure `import os` exists. For simplicity in this demo,
            # we can inject it at the top or assume it's there. 
            import_os = cst.SimpleStatementLine(body=[cst.Import(names=[cst.ImportAlias(name=cst.Name("os"))])])
            new_body = [import_os] + list(tree.body)
            tree = tree.with_changes(body=tuple(new_body))
            modified = True

    if modified:
        return tree.code
    return None


def fix_requirements(filepath: str) -> str | None:
    """Rewrite requirements.txt to pin non-pinned dependencies."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return None

    modified = False
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-") or stripped.startswith("git+"):
            new_lines.append(line)
            continue
            
        import re
        match = re.match(r"^([A-Za-z0-9_.\-]+)", stripped)
        if match and "==" not in stripped:
            pkg = match.group(1)
            # Find latest version
            version = get_latest_pypi_version(pkg)
            if version:
                new_line = f"{pkg}=={version}\n"
                new_lines.append(new_line)
                modified = True
                continue

        new_lines.append(line)

    if modified:
        return "".join(new_lines)
    return None


def generate_patch(original_dir: str, modified_files: dict[str, str]) -> str:
    """Generate a unified diff patch string from a dictionary of modified files."""
    patch_lines = []
    
    for rel_path, new_content in modified_files.items():
        abs_path = os.path.join(original_dir, rel_path)
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                old_content = f.read()
        except OSError:
            old_content = ""

        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines, new_lines, 
            fromfile=f"a/{rel_path}", 
            tofile=f"b/{rel_path}",
            n=3
        )
        patch_lines.extend(diff)

    return "".join(patch_lines)


def remediate_issues(repo_path: str, issues: list[Issue]) -> str | None:
    """
    Main entry point for auto-remediation.
    Reads issues, modifies files in memory, and generates a unified patch.
    Returns the patch string or None if nothing could be remediated.
    """
    modified_files: dict[str, str] = {}
    
    # Group issues by file
    issues_by_file: dict[str, list[Issue]] = {}
    for issue in issues:
        if issue.file:
            issues_by_file.setdefault(issue.file, []).append(issue)
        else:
            # Global issues (like missing seed without specific file)
            # Just attach to main.py or any py file if exists
            pass

    # Look for a global determinism issue that didn't have a file attached
    global_seed_issue = next((i for i in issues if i.rule == "determinism" and not i.file and "no reachable seed" in i.message.lower()), None)
    
    if global_seed_issue:
        # Find the first .py file that might be the main script
        py_files = []
        for root, _, files in os.walk(repo_path):
            if ".venv" in root or "node_modules" in root: continue
            for f in files:
                if f.endswith(".py"):
                    py_files.append(os.path.relpath(os.path.join(root, f), repo_path))
        
        # Prioritize main.py or train.py
        target = next((f for f in py_files if "main" in f or "train" in f), None)
        if not target and py_files: target = py_files[0]
        
        if target:
            issue_copy = Issue(**global_seed_issue.model_dump())
            issue_copy.file = target
            issues_by_file.setdefault(target, []).append(issue_copy)

    for rel_path, file_issues in issues_by_file.items():
        abs_path = os.path.join(repo_path, rel_path)
        
        if rel_path.endswith(".py"):
            new_code = fix_python_file(abs_path, file_issues)
            if new_code:
                modified_files[rel_path] = new_code
                
        elif rel_path == "requirements.txt" or rel_path.endswith("/requirements.txt"):
            new_content = fix_requirements(abs_path)
            if new_content:
                modified_files[rel_path] = new_content

    if modified_files:
        return generate_patch(repo_path, modified_files)
    
    return None
