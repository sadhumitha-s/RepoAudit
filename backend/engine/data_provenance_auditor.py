"""
Data Provenance Auditing.

Detects how data is loaded, checks if data URLs are alive, flags gated datasets,
and detects non-deterministic preprocessing pipelines.
"""

from __future__ import annotations
import ast
import os
import logging
import re
import httpx
from dataclasses import dataclass, field
from typing import Any

from models import Issue
from engine.utils import skip_ignored_dirs

logger = logging.getLogger(__name__)

# Common data loading functions to monitor
DATA_LOAD_FUNCTIONS = {
    "pandas": {"read_csv", "read_excel", "read_json", "read_parquet", "read_feather", "read_hdf", "read_sql", "read_table"},
    "numpy": {"load", "loadtxt", "genfromtxt"},
    "torch": {"load"},
    "datasets": {"load_dataset"},
    "urllib.request": {"urlretrieve"},
    "requests": {"get", "post"},
}

_DATA_LOAD_TARGETS: set[str] = set()
for _module, _fns in DATA_LOAD_FUNCTIONS.items():
    for _fn in _fns:
        _DATA_LOAD_TARGETS.add(f"{_module}.{_fn}")
        _DATA_LOAD_TARGETS.add(_fn)  # Also match bare function names
        if _module == "pandas":
            _DATA_LOAD_TARGETS.add(f"pd.{_fn}")
        if _module == "numpy":
            _DATA_LOAD_TARGETS.add(f"np.{_fn}")

# Known gated/TOS datasets on HuggingFace Hub (partial list for demonstration)
GATED_HF_DATASETS = {
    "meta-llama/Llama-2-7b",
    "meta-llama/Llama-2-13b",
    "meta-llama/Llama-2-70b",
    "meta-llama/Llama-3-8B",
    "meta-llama/Llama-3-70B",
    "mistralai/Mistral-7B-v0.1",
}

@dataclass
class DataLoadCall:
    target: str
    line: int
    args: list[Any] = field(default_factory=list)
    kwargs: dict[str, Any] = field(default_factory=dict)

@dataclass
class ShuffleCall:
    target: str
    line: int
    has_seed: bool

@dataclass
class ProvenanceAuditResult:
    file: str
    data_loads: list[DataLoadCall] = field(default_factory=list)
    shuffles: list[ShuffleCall] = field(default_factory=list)
    parse_error: str | None = None

class _ProvenanceVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.data_loads: list[DataLoadCall] = []
        self.shuffles: list[ShuffleCall] = []

    def _resolve_call_name(self, node: ast.Call) -> str | None:
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

    def _get_arg_value(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return f"var:{node.id}"
        return "complex_expression"

    def visit_Call(self, node: ast.Call) -> None:
        name = self._resolve_call_name(node)
        if name:
            # Detect data loading
            if name in _DATA_LOAD_TARGETS:
                args = [self._get_arg_value(arg) for arg in node.args]
                kwargs = {kw.arg: self._get_arg_value(kw.value) for kw in node.keywords if kw.arg}
                self.data_loads.append(DataLoadCall(target=name, line=node.lineno, args=args, kwargs=kwargs))

            # Detect shuffling
            if "shuffle" in name.lower() or "DataLoader" in name:
                has_seed = False
                # Check for seed, random_state, generator
                seed_keywords = {"random_state", "seed", "generator", "random_seed"}
                for kw in node.keywords:
                    if kw.arg in seed_keywords:
                        has_seed = True
                        break
                
                # Special case for DataLoader: shuffle=True/False
                is_shuffling = False
                if "DataLoader" in name:
                    for kw in node.keywords:
                        if kw.arg == "shuffle" and self._get_arg_value(kw.value) is True:
                            is_shuffling = True
                        if kw.arg == "generator" or kw.arg == "worker_init_fn":
                            # generator or worker_init_fn might be used for determinism
                            pass 

                if "shuffle" in name.lower() or is_shuffling:
                    # If it's a shuffle operation, check if seed is provided
                    self.shuffles.append(ShuffleCall(target=name, line=node.lineno, has_seed=has_seed))

        self.generic_visit(node)

def _is_url(path: str) -> bool:
    if not isinstance(path, str):
        return False
    return path.startswith(("http://", "https://", "s3://", "gs://"))

def _check_url_alive(url: str) -> bool:
    if not url.startswith(("http://", "https://")):
        return True # Assume S3/GS are managed elsewhere or skip for now
    try:
        response = httpx.head(url, timeout=5, follow_redirects=True)
        return response.status_code < 400
    except Exception:
        return False

def audit_file(filepath: str) -> ProvenanceAuditResult:
    rel_path = filepath
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
    except OSError as e:
        return ProvenanceAuditResult(file=rel_path, parse_error=str(e))

    if not source.strip():
        return ProvenanceAuditResult(file=rel_path)

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as e:
        return ProvenanceAuditResult(file=rel_path, parse_error=str(e))

    visitor = _ProvenanceVisitor()
    visitor.visit(tree)

    return ProvenanceAuditResult(
        file=rel_path,
        data_loads=visitor.data_loads,
        shuffles=visitor.shuffles,
    )

def audit_directory(repo_path: str) -> tuple[list[ProvenanceAuditResult], list[Issue]]:
    results: list[ProvenanceAuditResult] = []
    issues: list[Issue] = []

    target_files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(repo_path):
        skip_ignored_dirs(dirnames)
        for fname in filenames:
            if fname.endswith(".py"):
                target_files.append(os.path.join(dirpath, fname))

    for fpath in target_files:
        result = audit_file(fpath)
        results.append(result)
        rel = os.path.relpath(fpath, repo_path)

        # Check data loads
        for dl in result.data_loads:
            # Check for URLs
            for arg in dl.args:
                if _is_url(arg):
                    if not _check_url_alive(arg):
                        issues.append(Issue(
                            rule="provenance",
                            severity="warning",
                            file=rel,
                            line=dl.line,
                            message=f"Data URL `{arg}` appears to be dead or inaccessible.",
                            fix="Verify the data URL and update it if necessary."
                        ))
            
            # Check for gated HF datasets
            if dl.target in ("datasets.load_dataset", "load_dataset"):
                if dl.args and isinstance(dl.args[0], str):
                    ds_name = dl.args[0]
                    if ds_name in GATED_HF_DATASETS:
                        issues.append(Issue(
                            rule="provenance",
                            severity="info",
                            file=rel,
                            line=dl.line,
                            message=f"HuggingFace dataset `{ds_name}` is gated and requires authentication/TOS acceptance.",
                            fix="Ensure you have the necessary permissions and HF_TOKEN configured."
                        ))

        # Check for non-deterministic shuffling
        for sh in result.shuffles:
            if not sh.has_seed:
                issues.append(Issue(
                    rule="provenance",
                    severity="warning",
                    file=rel,
                    line=sh.line,
                    message=f"Non-deterministic shuffling detected in `{sh.target}` (no seed/random_state found).",
                    fix=f"Add a fixed seed (e.g., `random_state=42`) to `{sh.target}`."
                ))

    return results, issues
