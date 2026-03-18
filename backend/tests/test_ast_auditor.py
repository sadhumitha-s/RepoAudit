import os
import pytest
from engine.ast_auditor import audit_file, audit_directory


class TestAuditFile:
    def test_reachable_seed_global_scope(self, py_file):
        path = py_file("train.py", """
import torch
torch.manual_seed(42)
model = torch.nn.Linear(10, 5)
""")
        result = audit_file(path)
        assert len(result.seed_calls) == 1
        assert result.seed_calls[0].reachable is True
        assert result.seed_calls[0].scope == "global"

    def test_reachable_seed_in_main_guard(self, py_file):
        path = py_file("train.py", """
import torch

if __name__ == "__main__":
    torch.manual_seed(42)
    model = torch.nn.Linear(10, 5)
""")
        result = audit_file(path)
        assert len(result.seed_calls) == 1
        assert result.seed_calls[0].reachable is True
        assert result.seed_calls[0].scope == "main_guard"

    def test_unreachable_seed_in_function(self, py_file):
        path = py_file("train.py", """
import torch

def setup():
    torch.manual_seed(42)

model = torch.nn.Linear(10, 5)
""")
        result = audit_file(path)
        assert len(result.seed_calls) == 1
        assert result.seed_calls[0].reachable is False
        assert result.seed_calls[0].scope == "function"

    def test_unreachable_seed_in_conditional(self, py_file):
        path = py_file("train.py", """
import torch

if False:
    torch.manual_seed(42)

x = torch.randn(10)
""")
        result = audit_file(path)
        assert len(result.seed_calls) == 1
        assert result.seed_calls[0].reachable is False

    def test_numpy_seed(self, py_file):
        path = py_file("train.py", """
import numpy as np
np.random.seed(42)
data = np.random.randn(100)
""")
        result = audit_file(path)
        assert len(result.seed_calls) == 1
        assert result.seed_calls[0].target == "np.random.seed"
        assert result.seed_calls[0].reachable is True

    def test_multiple_frameworks(self, py_file):
        path = py_file("train.py", """
import torch
import numpy as np
import random

random.seed(42)
np.random.seed(42)
torch.manual_seed(42)
""")
        result = audit_file(path)
        assert len(result.seed_calls) == 3
        assert all(sc.reachable for sc in result.seed_calls)

    def test_detects_random_ops(self, py_file):
        path = py_file("train.py", """
import torch
x = torch.randn(10, 10)
""")
        result = audit_file(path)
        assert result.has_random_ops is True

    def test_empty_file(self, py_file):
        path = py_file("empty.py", "")
        result = audit_file(path)
        assert len(result.seed_calls) == 0
        assert result.parse_error is None

    def test_syntax_error(self, py_file):
        path = py_file("bad.py", "def foo(\n  invalid syntax here")
        result = audit_file(path)
        assert result.parse_error is not None

    def test_seed_in_class_method(self, py_file):
        path = py_file("model.py", """
import torch

class Trainer:
    def init_seeds(self):
        torch.manual_seed(42)
""")
        result = audit_file(path)
        assert len(result.seed_calls) == 1
        assert result.seed_calls[0].reachable is False
        assert result.seed_calls[0].scope == "function"

    def test_reversed_main_guard(self, py_file):
        path = py_file("train.py", """
import torch

if "__main__" == __name__:
    torch.manual_seed(42)
""")
        result = audit_file(path)
        assert len(result.seed_calls) == 1
        assert result.seed_calls[0].reachable is True


class TestAuditDirectory:
    def test_no_python_files(self, tmp_repo):
        os.makedirs(os.path.join(tmp_repo, "data"))
        with open(os.path.join(tmp_repo, "README.md"), "w") as f:
            f.write("# Hello")
        _, issues = audit_directory(str(tmp_repo))
        assert any("No supported source files" in i.message for i in issues)

    def test_random_ops_without_seed(self, tmp_repo, py_file):
        py_file("train.py", """
import torch
x = torch.randn(10)
model = torch.nn.Linear(10, 5)
""")
        _, issues = audit_directory(str(tmp_repo))
        assert any(i.severity == "critical" for i in issues)
        assert any("no reachable seed" in i.message.lower() for i in issues)

    def test_clean_repo(self, tmp_repo, py_file):
        py_file("train.py", """
import torch
torch.manual_seed(42)
x = torch.randn(10)
""")
        _, issues = audit_directory(str(tmp_repo))
        critical = [i for i in issues if i.severity == "critical"]
        assert len(critical) == 0