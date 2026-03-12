"""
Cross-file import graph and execution flow analysis.

Builds a directed graph of imports across all Python files in a repo,
traces execution flow from entry points, and determines whether seed
calls in utility modules are actually reachable from the main path.
"""

from __future__ import annotations
import ast
import os
import logging
from dataclasses import dataclass, field

from models import Issue

logger = logging.getLogger(__name__)

# Common entry-point filenames
_ENTRY_POINTS = {
    "main.py", "train.py", "run.py", "app.py",
    "test.py", "evaluate.py", "eval.py", "inference.py",
    "predict.py", "demo.py", "setup.py",
}


@dataclass
class ModuleInfo:
    """Parsed information about a single Python module."""
    filepath: str
    rel_path: str
    module_name: str        # Dotted module name (e.g. "utils.seed")
    imports: set[str] = field(default_factory=set)        # Modules this file imports
    imported_names: dict[str, str] = field(default_factory=dict)  # name -> source module
    defines_functions: set[str] = field(default_factory=set)
    defines_classes: set[str] = field(default_factory=set)
    calls_made: list[CallInfo] = field(default_factory=list)
    has_main_guard: bool = False
    is_entry_point: bool = False
    seed_calls_in_functions: dict[str, list[int]] = field(default_factory=dict)


@dataclass
class CallInfo:
    """A function/method call found in a module."""
    name: str          # e.g. "setup_seed" or "utils.setup_seed"
    line: int
    scope: str         # "global", "main_guard", "function:<name>", "class:<name>"


@dataclass
class ImportEdge:
    """A directed edge in the import graph."""
    source: str        # Importing module
    target: str        # Imported module
    names: set[str] = field(default_factory=set)  # Specific names imported (if any)


@dataclass
class FlowTrace:
    """Result of tracing execution from an entry point."""
    entry_point: str
    reachable_modules: set[str] = field(default_factory=set)
    reachable_seed_calls: list[dict] = field(default_factory=list)
    unreachable_seed_calls: list[dict] = field(default_factory=list)
    circular_imports: list[tuple[str, str]] = field(default_factory=list)
    call_chain: list[str] = field(default_factory=list)  # Ordered chain of calls


@dataclass
class ImportGraphResult:
    """Full result of the import graph analysis."""
    modules: dict[str, ModuleInfo] = field(default_factory=dict)
    edges: list[ImportEdge] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    flow_traces: list[FlowTrace] = field(default_factory=list)
    circular_imports: list[tuple[str, str]] = field(default_factory=list)


class _ModuleVisitor(ast.NodeVisitor):
    """Extract imports, function defs, class defs, calls, and seed locations."""

    def __init__(self, module_name: str) -> None:
        self.module_name = module_name
        self.imports: set[str] = set()
        self.imported_names: dict[str, str] = {}
        self.functions: set[str] = set()
        self.classes: set[str] = set()
        self.calls: list[CallInfo] = []
        self.has_main_guard: bool = False
        self.seed_in_functions: dict[str, list[int]] = {}
        self._scope_stack: list[str] = ["global"]
        self._current_func: str | None = None

    def _current_scope(self) -> str:
        return self._scope_stack[-1]

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            top = alias.name.split(".")[0]
            self.imports.add(alias.name)
            if alias.asname:
                self.imported_names[alias.asname] = alias.name
            else:
                self.imported_names[top] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self.imports.add(node.module)
            top = node.module.split(".")[0]
            self.imports.add(top)
            if node.names:
                for alias in node.names:
                    name = alias.asname or alias.name
                    self.imported_names[name] = f"{node.module}.{alias.name}"
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.functions.add(node.name)
        prev_func = self._current_func
        self._current_func = node.name
        self._scope_stack.append(f"function:{node.name}")
        self.generic_visit(node)
        self._scope_stack.pop()
        self._current_func = prev_func

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.classes.add(node.name)
        self._scope_stack.append(f"class:{node.name}")
        self.generic_visit(node)
        self._scope_stack.pop()

    def visit_If(self, node: ast.If) -> None:
        if self._is_main_guard(node):
            self.has_main_guard = True
            self._scope_stack.append("main_guard")
            for child in node.body:
                self.visit(child)
            self._scope_stack.pop()
            for child in node.orelse:
                self.visit(child)
        else:
            self.generic_visit(node)

    def _is_main_guard(self, node: ast.If) -> bool:
        test = node.test
        if not isinstance(test, ast.Compare):
            return False
        if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
            return False
        if len(test.comparators) != 1:
            return False
        left = test.left
        comp = test.comparators[0]

        def _is_name(n: ast.expr) -> bool:
            return (isinstance(n, ast.Name) and n.id == "__name__") or \
                   (isinstance(n, ast.Constant) and n.value == "__name__")

        def _is_main(n: ast.expr) -> bool:
            return isinstance(n, ast.Constant) and n.value == "__main__"

        return (_is_name(left) and _is_main(comp)) or \
               (_is_main(left) and _is_name(comp))

    def visit_Call(self, node: ast.Call) -> None:
        name = self._resolve_call_name(node)
        if name:
            self.calls.append(CallInfo(
                name=name,
                line=node.lineno,
                scope=self._current_scope(),
            ))
            # Track seed calls inside functions
            if self._current_func and _is_seed_call(name):
                if self._current_func not in self.seed_in_functions:
                    self.seed_in_functions[self._current_func] = []
                self.seed_in_functions[self._current_func].append(node.lineno)
        self.generic_visit(node)

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


# Seed call detection (reusing ast_auditor's knowledge)
_SEED_NAMES = {
    "torch.manual_seed", "torch.cuda.manual_seed", "torch.cuda.manual_seed_all",
    "np.random.seed", "numpy.random.seed", "random.seed",
    "tf.random.set_seed", "tensorflow.random.set_seed",
}


def _is_seed_call(name: str) -> bool:
    return name in _SEED_NAMES


def _filepath_to_module(filepath: str, repo_path: str) -> str:
    """Convert a file path to a Python module name."""
    rel = os.path.relpath(filepath, repo_path)
    # Remove .py extension
    if rel.endswith(".py"):
        rel = rel[:-3]
    # Replace path separators with dots
    module = rel.replace(os.sep, ".")
    # Remove __init__ suffix
    if module.endswith(".__init__"):
        module = module[:-9]
    return module


def _parse_module(filepath: str, repo_path: str) -> ModuleInfo | None:
    """Parse a single Python file into ModuleInfo."""
    rel_path = os.path.relpath(filepath, repo_path)
    module_name = _filepath_to_module(filepath, repo_path)

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
    except OSError:
        return None

    if not source.strip():
        return ModuleInfo(
            filepath=filepath, rel_path=rel_path, module_name=module_name
        )

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError:
        return ModuleInfo(
            filepath=filepath, rel_path=rel_path, module_name=module_name
        )

    visitor = _ModuleVisitor(module_name)
    visitor.visit(tree)

    basename = os.path.basename(filepath).lower()
    is_entry = basename in _ENTRY_POINTS or visitor.has_main_guard

    return ModuleInfo(
        filepath=filepath,
        rel_path=rel_path,
        module_name=module_name,
        imports=visitor.imports,
        imported_names=visitor.imported_names,
        defines_functions=visitor.functions,
        defines_classes=visitor.classes,
        calls_made=visitor.calls,
        has_main_guard=visitor.has_main_guard,
        is_entry_point=is_entry,
        seed_calls_in_functions=visitor.seed_in_functions,
    )


def build_import_graph(repo_path: str) -> ImportGraphResult:
    """Build a full import graph for all Python files in the repo."""
    result = ImportGraphResult()

    # Collect all Python files
    py_files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(repo_path):
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".")
            and d not in ("venv", ".venv", "env", "node_modules", "__pycache__")
        ]
        for fname in filenames:
            if fname.endswith(".py"):
                py_files.append(os.path.join(dirpath, fname))

    if not py_files:
        return result

    # Parse all modules
    all_module_names: set[str] = set()
    for fpath in py_files:
        info = _parse_module(fpath, repo_path)
        if info:
            result.modules[info.module_name] = info
            all_module_names.add(info.module_name)
            if info.is_entry_point:
                result.entry_points.append(info.module_name)

    # Build edges (only for intra-repo imports)
    for mod_name, mod_info in result.modules.items():
        for imp in mod_info.imports:
            # Check if the import resolves to a local module
            target = _resolve_local_import(imp, all_module_names)
            if target and target != mod_name:
                names = set()
                for local_name, source in mod_info.imported_names.items():
                    if source.startswith(imp):
                        names.add(local_name)
                result.edges.append(ImportEdge(
                    source=mod_name, target=target, names=names
                ))

    # Detect circular imports
    result.circular_imports = _detect_cycles(result)

    # Trace execution flow from each entry point
    for ep in result.entry_points:
        trace = _trace_execution(ep, result)
        result.flow_traces.append(trace)

    return result


def _resolve_local_import(import_name: str, local_modules: set[str]) -> str | None:
    """Resolve an import to a local module name, or None if external."""
    # Direct match
    if import_name in local_modules:
        return import_name
    # Try the top-level part
    top = import_name.split(".")[0]
    if top in local_modules:
        return top
    # Try matching as a submodule
    for mod in local_modules:
        if mod.startswith(import_name + ".") or import_name.startswith(mod + "."):
            return mod
    return None


def _detect_cycles(graph: ImportGraphResult) -> list[tuple[str, str]]:
    """Detect circular imports using DFS."""
    cycles: list[tuple[str, str]] = []
    # Build adjacency list
    adj: dict[str, set[str]] = {}
    for edge in graph.edges:
        if edge.source not in adj:
            adj[edge.source] = set()
        adj[edge.source].add(edge.target)

    visited: set[str] = set()
    in_stack: set[str] = set()

    def dfs(node: str) -> None:
        visited.add(node)
        in_stack.add(node)
        for neighbor in adj.get(node, set()):
            if neighbor in in_stack:
                cycles.append((node, neighbor))
            elif neighbor not in visited:
                dfs(neighbor)
        in_stack.discard(node)

    for mod in graph.modules:
        if mod not in visited:
            dfs(mod)

    return cycles


def _trace_execution(
    entry_module: str,
    graph: ImportGraphResult,
) -> FlowTrace:
    """
    Trace execution flow from an entry point through the import graph.
    Determines which seed calls in other modules are reachable.
    """
    trace = FlowTrace(entry_point=entry_module)
    visited: set[str] = set()
    # Build adjacency
    adj: dict[str, set[str]] = {}
    for edge in graph.edges:
        if edge.source not in adj:
            adj[edge.source] = set()
        adj[edge.source].add(edge.target)

    # BFS to find all reachable modules
    queue = [entry_module]
    visited.add(entry_module)
    while queue:
        current = queue.pop(0)
        trace.reachable_modules.add(current)
        for neighbor in adj.get(current, set()):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    entry_info = graph.modules.get(entry_module)
    if not entry_info:
        return trace

    # Collect all function calls made from global/main_guard scope in the entry point
    entry_callable_names: set[str] = set()
    for call in entry_info.calls_made:
        if call.scope in ("global", "main_guard"):
            entry_callable_names.add(call.name)
            # Also add the bare function name (e.g. "setup_seed" from "utils.setup_seed")
            if "." in call.name:
                entry_callable_names.add(call.name.split(".")[-1])

    # Now check: for each reachable module, do its seed-containing functions
    # get called from the entry point?
    for mod_name in trace.reachable_modules:
        mod_info = graph.modules.get(mod_name)
        if not mod_info:
            continue

        for func_name, seed_lines in mod_info.seed_calls_in_functions.items():
            # Check if this function is called from the entry point's main flow
            is_called = _is_function_called(
                func_name, mod_name, entry_info, graph
            )

            for line in seed_lines:
                record = {
                    "module": mod_name,
                    "file": mod_info.rel_path,
                    "function": func_name,
                    "line": line,
                    "called_from_entry": is_called,
                }
                if is_called:
                    trace.reachable_seed_calls.append(record)
                else:
                    trace.unreachable_seed_calls.append(record)

    # Check for circular imports involving this entry point
    for a, b in graph.circular_imports:
        if a in trace.reachable_modules or b in trace.reachable_modules:
            trace.circular_imports.append((a, b))

    return trace


def _is_function_called(
    func_name: str,
    func_module: str,
    entry_info: ModuleInfo,
    graph: ImportGraphResult,
    _depth: int = 0,
) -> bool:
    """
    Check if a function defined in func_module is called from the entry point.
    Traces through intermediate calls up to 3 levels deep.
    """
    if _depth > 3:
        return False

    # Direct calls from entry point
    for call in entry_info.calls_made:
        if call.scope not in ("global", "main_guard"):
            continue
        # Exact match: module.func_name or just func_name
        if call.name == func_name:
            return True
        if call.name == f"{func_module}.{func_name}":
            return True
        # Check via imported name aliasing
        if call.name in entry_info.imported_names:
            resolved = entry_info.imported_names[call.name]
            if resolved.endswith(f".{func_name}"):
                return True
        # Check if calling the bare name which was imported from func_module
        bare = call.name.split(".")[-1]
        if bare == func_name:
            source = entry_info.imported_names.get(bare, "")
            if func_module in source:
                return True

    # Check indirect calls: entry calls funcA(), funcA() calls our target
    if _depth < 3:
        for call in entry_info.calls_made:
            if call.scope not in ("global", "main_guard"):
                continue
            called_func = call.name.split(".")[-1]
            # Find which module defines this called function
            for mod_name, mod_info in graph.modules.items():
                if called_func in mod_info.defines_functions:
                    # Check if that function calls our target
                    for inner_call in mod_info.calls_made:
                        if inner_call.scope.startswith(f"function:{called_func}"):
                            inner_bare = inner_call.name.split(".")[-1]
                            if inner_bare == func_name:
                                return True

    return False


def audit_import_graph(repo_path: str) -> tuple[ImportGraphResult, list[Issue]]:
    """
    Build import graph and generate issues for:
    - Circular imports
    - Seed calls in utility functions that are never called from entry points
    - Missing entry points
    """
    graph = build_import_graph(repo_path)
    issues: list[Issue] = []

    if not graph.modules:
        return graph, issues

    # Issue: No entry points detected
    if not graph.entry_points:
        issues.append(Issue(
            rule="execution_flow",
            severity="warning",
            message=(
                "No entry point detected (no main.py, train.py, or "
                "`if __name__ == '__main__':` guard found). "
                "Cannot trace execution flow."
            ),
            fix=(
                "Add an entry point like `train.py` or add "
                "`if __name__ == '__main__':` to your main script."
            ),
        ))

    # Issue: Circular imports
    seen_cycles: set[tuple[str, str]] = set()
    for a, b in graph.circular_imports:
        pair = (min(a, b), max(a, b))
        if pair not in seen_cycles:
            seen_cycles.add(pair)
            # Find the files
            file_a = graph.modules.get(a, ModuleInfo(
                filepath="", rel_path=a, module_name=a
            )).rel_path
            file_b = graph.modules.get(b, ModuleInfo(
                filepath="", rel_path=b, module_name=b
            )).rel_path
            issues.append(Issue(
                rule="circular_import",
                severity="warning",
                file=file_a,
                message=(
                    f"Circular import detected between `{a}` and `{b}`. "
                    f"This can cause ImportError at runtime and makes "
                    f"execution order unpredictable."
                ),
                fix=(
                    f"Break the circular dependency by extracting shared code "
                    f"into a separate module, or use lazy imports."
                ),
            ))

    # Issue: Seed calls in functions that are never called from entry points
    for trace in graph.flow_traces:
        for unreachable in trace.unreachable_seed_calls:
            issues.append(Issue(
                rule="determinism",
                severity="warning",
                file=unreachable["file"],
                line=unreachable["line"],
                message=(
                    f"Seed call in `{unreachable['function']}()` "
                    f"(module `{unreachable['module']}`) is not called from "
                    f"entry point `{trace.entry_point}`. "
                    f"Seeds will not execute during training."
                ),
                fix=(
                    f"Call `{unreachable['function']}()` from your entry point "
                    f"(`{trace.entry_point}`) before any random operations, or "
                    f"move the seed call to the entry point's global scope."
                ),
            ))

    # Issue: Module defines seed function but is never imported
    all_reachable: set[str] = set()
    for trace in graph.flow_traces:
        all_reachable |= trace.reachable_modules

    for mod_name, mod_info in graph.modules.items():
        if mod_info.seed_calls_in_functions and mod_name not in all_reachable:
            if not mod_info.is_entry_point:
                issues.append(Issue(
                    rule="determinism",
                    severity="warning",
                    file=mod_info.rel_path,
                    message=(
                        f"Module `{mod_name}` contains seed setup in "
                        f"{list(mod_info.seed_calls_in_functions.keys())} "
                        f"but is never imported by any entry point."
                    ),
                    fix=(
                        f"Import and call the seed function from your entry point, "
                        f"or move the seed logic into the entry point directly."
                    ),
                ))

    return graph, issues