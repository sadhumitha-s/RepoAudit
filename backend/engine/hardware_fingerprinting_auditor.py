"""
Hardware and Environment Fingerprinting Detection.

Detects code that attempts to uniquely identify the hardware or execution
environment, which is often used for anti-sandbox or anti-VM techniques.
"""

from __future__ import annotations
import ast
import os
import logging
from dataclasses import dataclass, field
from typing import Any

from models import Issue
from engine.utils import skip_ignored_dirs

logger = logging.getLogger(__name__)

# Sensitive functions that can be used for fingerprinting
FINGERPRINT_FUNCTIONS = {
    "uuid": {"getnode"},
    "platform": {"uname", "node", "machine", "processor", "system", "version", "release"},
    "os": {"uname", "getlogin", "getuid", "getgid"},
    "socket": {"gethostname", "gethostbyname", "gethostbyaddr"},
    "psutil": {"net_if_addrs", "cpu_freq", "disk_partitions", "virtual_memory", "net_if_stats"},
    "subprocess": {"run", "call", "check_call", "check_output", "Popen"},
}

# Sensitive files/paths often checked for environment info
SENSITIVE_PATHS = {
    "/proc/cpuinfo", "/proc/meminfo", "/proc/version", "/proc/net/dev",
    "/proc/self/status", "/proc/1/comm", "/proc/sys/kernel/random/boot_id",
    "/sys/class/dmi/id/product_name", "/sys/class/dmi/id/sys_vendor",
    "/sys/class/dmi/id/chassis_vendor", "/sys/class/dmi/id/bios_vendor",
    "/sys/class/dmi/id/board_vendor", "/sys/class/net/", "/etc/machine-id",
    "/var/lib/dbus/machine-id",
}

# Anti-VM / Anti-Sandbox strings (to be used with caution to avoid false positives)
VM_INDICATORS = {
    "vmware", "virtualbox", "vbox", "qemu", "kvm", "xen", "hyper-v",
}

@dataclass
class FingerprintCall:
    type: str
    target: str
    line: int
    evidence: str

@dataclass
class FingerprintAuditResult:
    file: str
    calls: list[FingerprintCall] = field(default_factory=list)
    parse_error: str | None = None

class _FingerprintVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.calls: list[FingerprintCall] = []

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

    def visit_Call(self, node: ast.Call) -> None:
        name = self._resolve_call_name(node)
        if name:
            # Basic function name matching
            base_name = name.split(".")[-1]
            found_module = None
            for module, fns in FINGERPRINT_FUNCTIONS.items():
                if base_name in fns:
                    found_module = module
                    break
            
            if found_module:
                if found_module == "subprocess":
                    cmd_args = []
                    if node.args:
                        first_arg = node.args[0]
                        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                            cmd_args.append(first_arg.value)
                        elif isinstance(first_arg, ast.List):
                            for elt in first_arg.elts:
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                    cmd_args.append(elt.value)
                    
                    dangerous_cmds = {
                        "dmidecode", "lscpu", "cpuid", "ifconfig", "ip", 
                        "hostnamectl", "hwinfo", "systemd-detect-virt"
                    }
                    for arg in cmd_args:
                        if any(d_cmd in arg.lower() for d_cmd in dangerous_cmds):
                            self.calls.append(FingerprintCall(
                                type="command",
                                target=name,
                                line=node.lineno,
                                evidence=f"Execution of system command for fingerprinting: {arg}"
                            ))
                else:
                    self.calls.append(FingerprintCall(
                        type="function",
                        target=name,
                        line=node.lineno,
                        evidence=f"Call to potentially fingerprinting function: {name}"
                    ))

        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str):
            val_lower = node.value.lower()
            # Check for sensitive paths
            for path in SENSITIVE_PATHS:
                if path in val_lower:
                    self.calls.append(FingerprintCall(
                        type="path",
                        target="string_literal",
                        line=node.lineno,
                        evidence=f"Access to sensitive system path: {node.value}"
                    ))
                    break
            
            # Check for VM indicators only if they appear in small strings (likely constants)
            if len(node.value) < 30:
                for indicator in VM_INDICATORS:
                    if indicator == val_lower:
                         self.calls.append(FingerprintCall(
                            type="indicator",
                            target="string_literal",
                            line=node.lineno,
                            evidence=f"Potential VM/Sandbox indicator string: {node.value}"
                        ))
                         break

        self.generic_visit(node)

def audit_file(filepath: str) -> FingerprintAuditResult:
    rel_path = filepath
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
    except OSError as e:
        return FingerprintAuditResult(file=rel_path, parse_error=str(e))

    if not source.strip():
        return FingerprintAuditResult(file=rel_path)

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as e:
        return FingerprintAuditResult(file=rel_path, parse_error=str(e))

    visitor = _FingerprintVisitor()
    visitor.visit(tree)

    return FingerprintAuditResult(
        file=rel_path,
        calls=visitor.calls,
    )

def audit_directory(repo_path: str) -> tuple[list[FingerprintAuditResult], list[Issue]]:
    results: list[FingerprintAuditResult] = []
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

        for call in result.calls:
            issues.append(Issue(
                rule="fingerprinting",
                severity="warning",
                file=rel,
                line=call.line,
                message=call.evidence,
                fix="Avoid environment-specific checks to ensure reproducibility across different machines."
            ))

    return results, issues
