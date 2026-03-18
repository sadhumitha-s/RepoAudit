"""
Determinism verification via AST analysis.

Checks that seeding functions (torch.manual_seed, np.random.seed, etc.)
are reachable from the main execution path — not hidden inside dead branches.
"""

from __future__ import annotations
import ast
import os
import logging
from dataclasses import dataclass, field

from models import Issue
from engine.parsers import get_r_parser, get_julia_parser, extract_python_from_ipynb

logger = logging.getLogger(__name__)

SEED_FUNCTIONS: dict[str, set[str]] = {
    "torch": {"manual_seed", "cuda.manual_seed", "cuda.manual_seed_all"},
    "numpy": {"random.seed"},
    "random": {"seed"},
    "tensorflow": {"random.set_seed", "set_random_seed"},
}

# Flattened dotted call targets for matching
_SEED_TARGETS: set[str] = set()
for _module, _fns in SEED_FUNCTIONS.items():
    for _fn in _fns:
        _SEED_TARGETS.add(f"{_module}.{_fn}")
        # Also match common aliases
        if _module == "numpy":
            _SEED_TARGETS.add(f"np.{_fn}")
        if _module == "tensorflow":
            _SEED_TARGETS.add(f"tf.{_fn}")


@dataclass
class SeedCall:
    target: str
    line: int
    reachable: bool
    scope: str  # "global", "main_guard", "function", "conditional"


@dataclass
class ASTAuditResult:
    file: str
    seed_calls: list[SeedCall] = field(default_factory=list)
    has_random_ops: bool = False
    parse_error: str | None = None


class _SeedVisitor(ast.NodeVisitor):
    """Walk AST to find seed calls and check reachability."""

    def __init__(self) -> None:
        self.seed_calls: list[SeedCall] = []
        self.has_random_ops: bool = False
        self._scope_stack: list[str] = ["global"]

    def _current_scope(self) -> str:
        return self._scope_stack[-1]

    def _is_main_guard(self, node: ast.If) -> bool:
        """Check if an If node is `if __name__ == "__main__":`."""
        test = node.test
        if not isinstance(test, ast.Compare):
            return False
        if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
            return False
        left = test.left
        comparators = test.comparators
        if len(comparators) != 1:
            return False

        def _is_name_ref(n: ast.expr) -> bool:
            if isinstance(n, ast.Name) and n.id == "__name__":
                return True
            if isinstance(n, ast.Constant) and n.value == "__name__":
                return True
            return False

        def _is_main_str(n: ast.expr) -> bool:
            return isinstance(n, ast.Constant) and n.value == "__main__"

        return (
            (_is_name_ref(left) and _is_main_str(comparators[0]))
            or (_is_main_str(left) and _is_name_ref(comparators[0]))
        )

    def _resolve_call_name(self, node: ast.Call) -> str | None:
        """Resolve a call node to a dotted string like 'torch.manual_seed'."""
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

    def visit_Call(self, node: ast.Call) -> None:
        name = self._resolve_call_name(node)
        if name:
            # Check if it's a seed call
            if name in _SEED_TARGETS:
                reachable = self._current_scope() in ("global", "main_guard")
                self.seed_calls.append(
                    SeedCall(
                        target=name,
                        line=node.lineno,
                        reachable=reachable,
                        scope=self._current_scope(),
                    )
                )

            # Check if random operations are used
            for module in ("torch", "np", "numpy", "random", "tf", "tensorflow"):
                if name.startswith(f"{module}.") and "seed" not in name.lower():
                    self.has_random_ops = True

        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._scope_stack.append("function")
        self.generic_visit(node)
        self._scope_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_If(self, node: ast.If) -> None:
        if self._is_main_guard(node):
            self._scope_stack.append("main_guard")
            for child in node.body:
                self.visit(child)
            self._scope_stack.pop()
            # orelse is outside the main guard
            self._scope_stack.append("conditional")
            for child in node.orelse:
                self.visit(child)
            self._scope_stack.pop()
        else:
            self._scope_stack.append("conditional")
            self.generic_visit(node)
            self._scope_stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._scope_stack.append("function")
        self.generic_visit(node)
        self._scope_stack.pop()


def _walk_tree_sitter(node, callback):
    callback(node)
    for child in node.children:
        _walk_tree_sitter(child, callback)

def _audit_r_file(filepath: str, source: str) -> ASTAuditResult:
    parser = get_r_parser()
    source_bytes = source.encode("utf8")
    tree = parser.parse(source_bytes)
    
    seed_calls = []
    has_random_ops = False

    def visit(node):
        nonlocal has_random_ops
        if node.type == "call":
            func_node = node.children[0]
            func_name = source_bytes[func_node.start_byte:func_node.end_byte].decode("utf8")
            
            if func_name == "set.seed":
                seed_calls.append(SeedCall(
                    target=func_name,
                    line=node.start_point[0] + 1,
                    reachable=True,
                    scope="global"
                ))
            elif "runif" in func_name or "rnorm" in func_name or "sample" in func_name:
                has_random_ops = True

    _walk_tree_sitter(tree.root_node, visit)
    return ASTAuditResult(file=filepath, seed_calls=seed_calls, has_random_ops=has_random_ops)

def _audit_julia_file(filepath: str, source: str) -> ASTAuditResult:
    parser = get_julia_parser()
    source_bytes = source.encode("utf8")
    tree = parser.parse(source_bytes)
    
    seed_calls = []
    has_random_ops = False

    def visit(node):
        nonlocal has_random_ops
        if node.type == "call_expression":
            func_node = node.children[0]
            func_name = source_bytes[func_node.start_byte:func_node.end_byte].decode("utf8")
            
            if func_name in ("Random.seed!", "seed!"):
                seed_calls.append(SeedCall(
                    target=func_name,
                    line=node.start_point[0] + 1,
                    reachable=True,
                    scope="global"
                ))
            elif "rand" in func_name or "randn" in func_name:
                has_random_ops = True

    _walk_tree_sitter(tree.root_node, visit)
    return ASTAuditResult(file=filepath, seed_calls=seed_calls, has_random_ops=has_random_ops)

def audit_file(filepath: str) -> ASTAuditResult:
    """Audit a single file for determinism."""
    rel_path = filepath
    
    if filepath.endswith(".ipynb"):
        source = extract_python_from_ipynb(filepath)
    else:
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
        except OSError as e:
            return ASTAuditResult(file=rel_path, parse_error=str(e))

    if not source.strip():
        return ASTAuditResult(file=rel_path)

    if filepath.endswith(".r"):
        return _audit_r_file(filepath, source)
    if filepath.endswith(".jl"):
        return _audit_julia_file(filepath, source)

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as e:
        msg = getattr(e, "msg", str(e))
        lineno = getattr(e, "lineno", "?")
        return ASTAuditResult(
            file=rel_path,
            parse_error=f"SyntaxError at line {lineno}: {msg}",
        )

    visitor = _SeedVisitor()
    visitor.visit(tree)

    return ASTAuditResult(
        file=rel_path,
        seed_calls=visitor.seed_calls,
        has_random_ops=visitor.has_random_ops,
    )


def audit_directory(repo_path: str) -> tuple[list[ASTAuditResult], list[Issue]]:
    """
    Audit all Python files in a repository for determinism issues.
    Returns (results, issues).
    """
    results: list[ASTAuditResult] = []
    issues: list[Issue] = []

    target_files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(repo_path):
        # Skip hidden dirs, venvs, test dirs
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".")
            and d not in ("venv", ".venv", "env", "node_modules", "__pycache__")
        ]
        for fname in filenames:
            if fname.endswith((".py", ".ipynb", ".r", ".jl")):
                target_files.append(os.path.join(dirpath, fname))

    if not target_files:
        issues.append(Issue(
            rule="determinism",
            severity="info",
            message="No supported source files (.py, .ipynb, .r, .jl) found.",
        ))
        return results, issues

    any_random_ops = False
    any_reachable_seed = False
    unreachable_seeds: list[SeedCall] = []

    for fpath in target_files:
        result = audit_file(fpath)
        results.append(result)

        rel = os.path.relpath(fpath, repo_path)

        if result.parse_error:
            issues.append(Issue(
                rule="determinism",
                severity="info",
                file=rel,
                message=f"Could not parse: {result.parse_error}",
            ))
            continue

        if result.has_random_ops:
            any_random_ops = True

        for sc in result.seed_calls:
            if sc.reachable:
                any_reachable_seed = True
            else:
                unreachable_seeds.append(sc)
                issues.append(Issue(
                    rule="determinism",
                    severity="warning",
                    file=rel,
                    line=sc.line,
                    message=(
                        f"Seed call `{sc.target}` at line {sc.line} is inside "
                        f"a '{sc.scope}' scope and may not execute on the main path."
                    ),
                    fix=(
                        f"Move `{sc.target}(...)` to the global scope or "
                        f"inside the `if __name__ == '__main__':` block."
                    ),
                ))

    # If random ops exist but no reachable seed was found
    if any_random_ops and not any_reachable_seed:
        issues.append(Issue(
            rule="determinism",
            severity="critical",
            message=(
                "Random operations detected but no reachable seed call found. "
                "Results will be non-deterministic."
            ),
            fix=(
                "Add a seed call (e.g. `torch.manual_seed(42)`) at the top of "
                "your main script or inside `if __name__ == '__main__':`."
            ),
        ))

    return results, issues