"""
Dependency auditing.

Checks for:
 - Presence and quality of requirements.txt / environment.yml / Dockerfile
 - Version pinning in requirements
 - Import analysis to detect potential missing dependencies
"""

from __future__ import annotations
import ast
import os
import re
import sys
import logging
from dataclasses import dataclass, field

from models import Issue
from engine.utils import skip_ignored_dirs
from engine.parsers import get_r_parser, get_julia_parser, extract_python_from_ipynb

logger = logging.getLogger(__name__)

# Known standard library top-level modules (Python 3.11)
_STDLIB_MODULES: set[str] = set(sys.stdlib_module_names) if hasattr(
    sys, "stdlib_module_names"
) else {
    "abc", "aifc", "argparse", "array", "ast", "asynchat", "asyncio",
    "asyncore", "atexit", "base64", "bdb", "binascii", "binhex", "bisect",
    "builtins", "bz2", "calendar", "cgi", "cgitb", "chunk", "cmath", "cmd",
    "code", "codecs", "codeop", "collections", "colorsys", "compileall",
    "concurrent", "configparser", "contextlib", "contextvars", "copy",
    "copyreg", "cProfile", "crypt", "csv", "ctypes", "curses", "dataclasses",
    "datetime", "dbm", "decimal", "difflib", "dis", "distutils", "doctest",
    "email", "encodings", "enum", "errno", "faulthandler", "fcntl",
    "filecmp", "fileinput", "fnmatch", "fractions", "ftplib", "functools",
    "gc", "getopt", "getpass", "gettext", "glob", "grp", "gzip", "hashlib",
    "heapq", "hmac", "html", "http", "idlelib", "imaplib", "imghdr", "imp",
    "importlib", "inspect", "io", "ipaddress", "itertools", "json",
    "keyword", "lib2to3", "linecache", "locale", "logging", "lzma",
    "mailbox", "mailcap", "marshal", "math", "mimetypes", "mmap",
    "modulefinder", "multiprocessing", "netrc", "nis", "nntplib", "numbers",
    "operator", "optparse", "os", "ossaudiodev", "pathlib", "pdb", "pickle",
    "pickletools", "pipes", "pkgutil", "platform", "plistlib", "poplib",
    "posix", "posixpath", "pprint", "profile", "pstats", "pty", "pwd",
    "py_compile", "pyclbr", "pydoc", "queue", "quopri", "random", "re",
    "readline", "reprlib", "resource", "rlcompleter", "runpy", "sched",
    "secrets", "select", "selectors", "shelve", "shlex", "shutil", "signal",
    "site", "smtpd", "smtplib", "sndhdr", "socket", "socketserver",
    "sqlite3", "ssl", "stat", "statistics", "string", "stringprep",
    "struct", "subprocess", "sunau", "symtable", "sys", "sysconfig",
    "syslog", "tabnanny", "tarfile", "telnetlib", "tempfile", "termios",
    "test", "textwrap", "threading", "time", "timeit", "tkinter", "token",
    "tokenize", "trace", "traceback", "tracemalloc", "tty", "turtle",
    "turtledemo", "types", "typing", "unicodedata", "unittest", "urllib",
    "uu", "uuid", "venv", "warnings", "wave", "weakref", "webbrowser",
    "winreg", "winsound", "wsgiref", "xdrlib", "xml", "xmlrpc", "zipapp",
    "zipfile", "zipimport", "zlib", "_thread",
}

# Common package name -> PyPI name mappings
_IMPORT_TO_PYPI: dict[str, str] = {
    "cv2": "opencv-python",
    "PIL": "Pillow",
    "sklearn": "scikit-learn",
    "skimage": "scikit-image",
    "yaml": "PyYAML",
    "attr": "attrs",
    "bs4": "beautifulsoup4",
    "git": "GitPython",
    "dotenv": "python-dotenv",
    "wx": "wxPython",
}


@dataclass
class DependencyAuditResult:
    has_requirements_txt: bool = False
    has_environment_yml: bool = False
    has_setup_py: bool = False
    has_pyproject_toml: bool = False
    has_dockerfile: bool = False
    has_r_description: bool = False
    has_r_renv: bool = False
    has_julia_project: bool = False
    pinned_count: int = 0
    unpinned_count: int = 0
    total_deps: int = 0
    detected_imports: set[str] = field(default_factory=set)
    declared_deps: set[str] = field(default_factory=set)
    missing_deps: set[str] = field(default_factory=set)


def _walk_tree_sitter(node, callback):
    callback(node)
    for child in node.children:
        _walk_tree_sitter(child, callback)

def _extract_imports(filepath: str) -> set[str]:
    """Extract top-level import module names from a supported file."""
    imports: set[str] = set()
    
    if filepath.endswith(".ipynb"):
        source = extract_python_from_ipynb(filepath)
    else:
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
        except OSError:
            return imports

    if filepath.endswith(".r"):
        parser = get_r_parser()
        source_bytes = source.encode("utf8")
        tree = parser.parse(source_bytes)
        def visit_r(node):
            if node.type == "call":
                func_node = node.children[0]
                func_name = source_bytes[func_node.start_byte:func_node.end_byte].decode("utf8")
                if func_name in ("library", "require") and len(node.children) > 1:
                    args_node = node.children[1]
                    # Best effort string matching for simplicity
                    text = source_bytes[args_node.start_byte:args_node.end_byte].decode("utf8")
                    match = re.search(r'["\']?([A-Za-z0-9_.]+)["\']?', text)
                    if match:
                        imports.add(match.group(1))
        _walk_tree_sitter(tree.root_node, visit_r)
        return imports

    if filepath.endswith(".jl"):
        parser = get_julia_parser()
        source_bytes = source.encode("utf8")
        tree = parser.parse(source_bytes)
        def visit_jl(node):
            if node.type in ("using_statement", "import_statement"):
                text = source_bytes[node.start_byte:node.end_byte].decode("utf8")
                # text is `using Foo, Bar` or `using Foo: bar`
                # strip `using ` and `import `
                names = re.sub(r'^(using|import)\s+', '', text)
                names = names.split(':')[0] # drop specific imports
                for name in names.split(','):
                    name = name.strip()
                    if name:
                        imports.add(name.split('.')[0])
        _walk_tree_sitter(tree.root_node, visit_jl)
        return imports

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError:
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                imports.add(top)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                imports.add(top)
    return imports


def _parse_requirements_txt(filepath: str) -> tuple[set[str], int, int]:
    """Parse requirements.txt, return (package_names, pinned_count, unpinned)."""
    packages: set[str] = set()
    pinned = 0
    unpinned = 0

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return packages, 0, 0

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Handle git+ URLs, extras, etc.
        if line.startswith("git+") or line.startswith("http"):
            continue

        # Split on version specifiers
        match = re.match(r"^([A-Za-z0-9_.\-]+)", line)
        if match:
            pkg = match.group(1).lower().replace("-", "_")
            packages.add(pkg)
            if re.search(r"==\d", line):
                pinned += 1
            else:
                unpinned += 1

    return packages, pinned, unpinned


def audit_directory(repo_path: str) -> tuple[DependencyAuditResult, list[Issue]]:
    """Audit dependency management in the repository."""
    result = DependencyAuditResult()
    issues: list[Issue] = []

    # Check for dependency files
    dep_files = {
        "requirements.txt": "has_requirements_txt",
        "environment.yml": "has_environment_yml",
        "environment.yaml": "has_environment_yml",
        "setup.py": "has_setup_py",
        "pyproject.toml": "has_pyproject_toml",
        "Dockerfile": "has_dockerfile",
        "DESCRIPTION": "has_r_description",
        "renv.lock": "has_r_renv",
        "Project.toml": "has_julia_project",
    }

    root_files = set(os.listdir(repo_path))
    for fname, attr in dep_files.items():
        if fname in root_files:
            setattr(result, attr, True)

    has_any_dep_file = (
        result.has_requirements_txt
        or result.has_environment_yml
        or result.has_setup_py
        or result.has_pyproject_toml
        or result.has_r_description
        or result.has_r_renv
        or result.has_julia_project
    )

    if not has_any_dep_file:
        issues.append(Issue(
            rule="dependency",
            severity="critical",
            message=(
                "No dependency file found (requirements.txt, environment.yml, "
                "setup.py, or pyproject.toml). Environment cannot be reproduced."
            ),
            fix=(
                "Create a `requirements.txt` with pinned versions:\n"
                "  pip freeze > requirements.txt"
            ),
        ))

    # Parse requirements.txt if present
    req_path = os.path.join(repo_path, "requirements.txt")
    if os.path.isfile(req_path):
        declared, pinned, unpinned = _parse_requirements_txt(req_path)
        result.declared_deps = declared
        result.pinned_count = pinned
        result.unpinned_count = unpinned
        result.total_deps = pinned + unpinned

        if unpinned > 0:
            issues.append(Issue(
                rule="dependency",
                severity="warning",
                file="requirements.txt",
                message=(
                    f"{unpinned} of {result.total_deps} dependencies are not "
                    f"pinned to exact versions (==)."
                ),
                fix=(
                    "Pin all dependencies to exact versions: "
                    "`package==1.2.3` instead of `package>=1.2`."
                ),
            ))

        if result.total_deps == 0:
            issues.append(Issue(
                rule="dependency",
                severity="warning",
                file="requirements.txt",
                message="requirements.txt exists but contains no packages.",
            ))

    # Collect all imports from supported files
    for dirpath, dirnames, filenames in os.walk(repo_path):
        skip_ignored_dirs(dirnames)
        for fname in filenames:
            if fname.endswith((".py", ".ipynb", ".r", ".jl")):
                fpath = os.path.join(dirpath, fname)
                result.detected_imports |= _extract_imports(fpath)

    # Filter out stdlib and local packages
    external_imports: set[str] = set()
    for imp in result.detected_imports:
        if imp in _STDLIB_MODULES:
            continue
        if imp.startswith("_"):
            continue
        # Check if it's a local module (directory or file in repo root)
        local_mod = os.path.join(repo_path, imp)
        if os.path.isdir(local_mod) or os.path.isfile(local_mod + ".py"):
            continue
        external_imports.add(imp)

    # Compare with declared deps
    if result.declared_deps:
        normalized_declared = {d.lower().replace("-", "_") for d in result.declared_deps}
        for imp in external_imports:
            pypi_name = _IMPORT_TO_PYPI.get(imp, imp)
            normalized_imp = pypi_name.lower().replace("-", "_")
            if normalized_imp not in normalized_declared:
                result.missing_deps.add(imp)

        if result.missing_deps:
            missing_list = ", ".join(sorted(result.missing_deps)[:10])
            extra = (
                f" (and {len(result.missing_deps) - 10} more)"
                if len(result.missing_deps) > 10
                else ""
            )
            issues.append(Issue(
                rule="dependency",
                severity="warning",
                message=(
                    f"Potentially undeclared dependencies: "
                    f"{missing_list}{extra}"
                ),
                fix="Add missing packages to requirements.txt with pinned versions.",
            ))

    return result, issues