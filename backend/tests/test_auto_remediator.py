import os
from engine.auto_remediator import remediate_issues
from models import Issue

def test_auto_remediator_python(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    
    py_file = repo / "main.py"
    py_code = 'print("hello")\npath = "C:\\\\Users\\\\foo\\\\data.csv"\n'
    py_file.write_text(py_code)

    req_file = repo / "requirements.txt"
    req_file.write_text("requests>=2.0\n")

    issues = [
        Issue(
            rule="determinism",
            severity="critical",
            file="main.py",
            message="no reachable seed found",
            fix="inject seed"
        ),
        Issue(
            rule="hardcoded_path",
            severity="warning",
            file="main.py",
            line=2,
            message="Hardcoded Windows path",
            fix="use os.path"
        ),
        Issue(
            rule="dependency",
            severity="warning",
            file="requirements.txt",
            message="unpinned dependency",
            fix="pin it"
        )
    ]

    patch = remediate_issues(str(repo), issues)
    
    assert patch is not None
    # Check that seed was injected
    assert "import torch" in patch
    assert "torch.manual_seed(42)" in patch
    # Check that path was rewritten
    assert "os.path.expanduser" in patch
    # Check that requirements was fixed
    assert "requests==" in patch

