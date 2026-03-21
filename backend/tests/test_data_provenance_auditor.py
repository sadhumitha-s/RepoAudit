import os
import pytest
from unittest.mock import patch, MagicMock
from engine.data_provenance_auditor import audit_file, audit_directory

class TestDataProvenanceAuditor:
    def test_detect_pandas_url(self, py_file):
        path = py_file("load_data.py", """
import pandas as pd
df = pd.read_csv("https://example.com/data.csv")
""")
        result = audit_file(path)
        assert len(result.data_loads) == 1
        assert result.data_loads[0].target == "pd.read_csv"
        assert result.data_loads[0].args[0] == "https://example.com/data.csv"

    def test_detect_hf_load_dataset(self, py_file):
        path = py_file("load_data.py", """
from datasets import load_dataset
ds = load_dataset("glue", "mrpc")
""")
        result = audit_file(path)
        assert len(result.data_loads) == 1
        assert result.data_loads[0].target == "load_dataset"
        assert result.data_loads[0].args[0] == "glue"

    def test_detect_nondeterministic_shuffle(self, py_file):
        path = py_file("train.py", """
import torch
from torch.utils.data import DataLoader
loader = DataLoader(dataset, batch_size=32, shuffle=True)
""")
        result = audit_file(path)
        assert len(result.shuffles) == 1
        assert result.shuffles[0].has_seed is False

    def test_detect_deterministic_shuffle(self, py_file):
        path = py_file("train.py", """
import torch
from torch.utils.data import DataLoader
loader = DataLoader(dataset, batch_size=32, shuffle=True, generator=torch.Generator().manual_seed(42))
""")
        # Note: My current implementation checks for 'generator' in keywords but doesn't set has_seed=True unless it's in seed_keywords
        # I should update the implementation to include 'generator' in seed_keywords
        result = audit_file(path)
        assert len(result.shuffles) == 1
        # In my current implementation, generator IS in seed_keywords. Let's verify.
        # seed_keywords = {"random_state", "seed", "generator", "random_seed"}
        assert result.shuffles[0].has_seed is True

    @patch("engine.data_provenance_auditor.httpx.head")
    def test_url_liveness_dead(self, mock_head, tmp_repo, py_file):
        mock_head.return_value.status_code = 404
        py_file("load_data.py", """
import pandas as pd
df = pd.read_csv("https://example.com/dead.csv")
""")
        _, issues = audit_directory(str(tmp_repo))
        assert any("appears to be dead" in i.message for i in issues)
        assert any(i.severity == "warning" for i in issues)

    def test_gated_hf_dataset(self, tmp_repo, py_file):
        py_file("load_data.py", """
from datasets import load_dataset
ds = load_dataset("meta-llama/Llama-2-7b")
""")
        _, issues = audit_directory(str(tmp_repo))
        assert any("is gated" in i.message for i in issues)
        assert any(i.severity == "info" for i in issues)

    def test_nondeterministic_shuffle_issue(self, tmp_repo, py_file):
        py_file("train.py", """
from sklearn.utils import shuffle
X, y = shuffle(X, y)
""")
        _, issues = audit_directory(str(tmp_repo))
        assert any("Non-deterministic shuffling detected" in i.message for i in issues)
        assert any(i.severity == "warning" for i in issues)
