import os
import pytest
from engine.hardware_fingerprinting_auditor import audit_file, audit_directory

def test_fingerprint_detection(tmp_path):
    # Create a dummy python file with fingerprinting code
    code = """
import uuid
import platform
import os
import subprocess

def check_env():
    node = uuid.getnode()
    sys = platform.uname()
    with open("/proc/cpuinfo", "r") as f:
        pass
    subprocess.run(["dmidecode"])
    is_vbox = "virtualbox" == platform.system().lower()
"""
    d = tmp_path / "test_repo"
    d.mkdir()
    f = d / "fingerprint.py"
    f.write_text(code)

    results, issues = audit_directory(str(d))
    
    # Check if we found issues
    assert len(issues) >= 5
    rules = [i.rule for i in issues]
    assert all(r == "fingerprinting" for r in rules)
    
    messages = [i.message.lower() for i in issues]
    assert any("uuid.getnode" in m for m in messages)
    assert any("platform.uname" in m for m in messages)
    assert any("/proc/cpuinfo" in m for m in messages)
    assert any("dmidecode" in m for m in messages)
    assert any("virtualbox" in m for m in messages)

def test_clean_file(tmp_path):
    code = """
def add(a, b):
    return a + b
"""
    d = tmp_path / "clean_repo"
    d.mkdir()
    f = d / "clean.py"
    f.write_text(code)

    results, issues = audit_directory(str(d))
    assert len(issues) == 0
