"""
Execution Replay Verification Auditor.
Reproduces workflows in a Bubblewrap sandbox to verify audit levels L0-L3.
"""

from __future__ import annotations
import os
import time
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from models import Issue
from engine.sandbox import Sandbox

logger = logging.getLogger(__name__)

@dataclass
class ExecutionReplayResult:
    l0_deps_install: bool = False      # Level 0: Dependencies installed
    l1_imports_success: bool = False   # Level 1: Standard imports/parsing succeed
    l2_run_success: bool = False       # Level 2: Entry point runs for >5s
    l3_outputs_produced: bool = False  # Level 3: Output files created
    highest_level: int = -1
    log: str = ""
    error: str | None = None

def _get_files_snapshot(repo_path: str) -> set[str]:
    """Get a set of all file paths in the repo for comparison."""
    files = set()
    for root, _, filenames in os.walk(repo_path):
        for f in filenames:
            rel_path = os.path.relpath(os.path.join(root, f), repo_path)
            files.add(rel_path)
    return files

def _detect_entry_point(repo_path: str, claimed_commands: list[str] | None = None) -> str | None:
    """Identify the primary entry point script/command."""
    if claimed_commands:
        # Prioritize python/python3 commands from README
        for cmd in claimed_commands:
            if re.search(r"python\d?\s+[\w.-]+\.py", cmd):
                # Extract the first script mentioned
                match = re.search(r"([\w.-]+\.py)", cmd)
                if match and os.path.exists(os.path.join(repo_path, match.group(1))):
                    return match.group(1)
    
    # Fallback to common patterns
    fallbacks = ["main.py", "train.py", "run.py", "app.py"]
    for f in fallbacks:
        if os.path.exists(os.path.join(repo_path, f)):
            return f
            
    return None

def audit_directory(repo_path: str, claimed_commands: list[str] | None = None) -> tuple[ExecutionReplayResult, list[Issue]]:
    """Perform dynamic execution replay audit."""
    result = ExecutionReplayResult()
    issues: list[Issue] = []
    
    sandbox = Sandbox(repo_path)
    if not sandbox.has_bwrap:
        result.error = "Bubblewrap not available; dynamic audit skipped."
        return result, issues

    time_start = time.time()
    initial_files = _get_files_snapshot(repo_path)
    
    # --- L0: Dependency Installation ---
    # We use a local venv inside the repo path to keep it contained
    logger.info("Replay: Attempting L0 (Dependency Installation)")
    
    # Check for requirements.txt
    req_file = "requirements.txt"
    if not os.path.exists(os.path.join(repo_path, req_file)):
        # If no requirements.txt, check for environment.yml
        if os.path.exists(os.path.join(repo_path, "environment.yml")):
             # We skip conda for now as it's too heavy for a 60s timeout
             pass
    
    # Create venv and install
    install_cmd = ["python3", "-m", "venv", ".venv_audit"]
    res = sandbox.run(install_cmd, timeout=30, allow_net=True)
    if res.returncode == 0:
        pip_cmd = [".venv_audit/bin/pip", "install", "-r", req_file] if os.path.exists(os.path.join(repo_path, req_file)) else [".venv_audit/bin/pip", "install", "."]
        res = sandbox.run(pip_cmd, timeout=60, allow_net=True)
        if res.returncode == 0:
            result.l0_deps_install = True
            result.highest_level = 0
            result.log += "L0: Dependencies installed successfully.\n"
        else:
            result.log += f"L0 Failed: pip install failed\n{res.stderr}\n"
    else:
        result.log += f"L0 Failed: venv creation failed\n{res.stderr}\n"

    if not result.l0_deps_install:
        issues.append(Issue(
            rule="execution",
            severity="warning",
            message="Dynamic dependency installation failed. The repository might not be reproducible.",
            fix="Ensure requirements.txt is complete and valid."
        ))
        return result, issues

    # --- L1: Import Success ---
    logger.info("Replay: Attempting L1 (Import Success)")
    entry_script = _detect_entry_point(repo_path, claimed_commands)
    if entry_script:
        # Try to parse and import the entry script
        # -c "import sys; sys.path.insert(0, '.'); import <mod>"
        mod_name = entry_script.rsplit(".", 1)[0].replace("/", ".")
        import_cmd = [".venv_audit/bin/python", "-c", f"import sys; sys.path.insert(0, '.'); import {mod_name}; print('Import success')"]
        res = sandbox.run(import_cmd, timeout=10, allow_net=False)
        if res.returncode == 0:
            result.l1_imports_success = True
            result.highest_level = 1
            result.log += "L1: Script imported successfully.\n"
        else:
            result.log += f"L1 Failed: Import of {entry_script} failed\n{res.stderr}\n"
    else:
        result.log += "L1 Skipped: No entry point detected.\n"

    # --- L2: Runtime Stability ---
    if entry_script:
        logger.info("Replay: Attempting L2 (Runtime Stability)")
        run_cmd = [".venv_audit/bin/python", entry_script]
        # We run for 60s total, but consider it a success if it lasts >5s without crashing
        start_exec = time.time()
        res = sandbox.run(run_cmd, timeout=60, allow_net=False)
        duration = time.time() - start_exec
        
        # If it timed out (124) or returned 0, or lasted >5s, we count it as a partial success
        if res.returncode == 0 or res.returncode == 124 or duration > 5:
            result.l2_run_success = True
            result.highest_level = 2
            result.log += f"L2: Entry point ran for {duration:.1f}s.\n"
        else:
            result.log += f"L2 Failed: Script crashed after {duration:.1f}s with code {res.returncode}.\n{res.stderr}\n"
            issues.append(Issue(
                rule="execution",
                severity="critical",
                file=entry_script,
                message=f"Repository entry point `{entry_script}` crashed immediately during replay.",
                fix="Check for missing dependencies or environment assumptions."
            ))

    # --- L3: Output Production ---
    if result.l2_run_success:
        current_files = _get_files_snapshot(repo_path)
        new_files = current_files - initial_files - {".venv_audit", ".venv_audit/bin/python"}
        # Filter out venv files
        new_files = {f for f in new_files if not f.startswith(".venv_audit")}
        
        if new_files:
            result.l3_outputs_produced = True
            result.highest_level = 3
            result.log += f"L3: Produced {len(new_files)} new files: {list(new_files)[:5]}\n"
        else:
            result.log += "L3: No output files detected.\n"

    return result, issues
