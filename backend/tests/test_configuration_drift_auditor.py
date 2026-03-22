import os
import pytest
import yaml
import json
from unittest.mock import MagicMock, patch
from engine.configuration_drift_auditor import audit_directory, ConfigurationDriftResult
from models import Issue

@pytest.fixture
def mock_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    
    # Create a config file
    config = {"epochs": 50, "learning_rate": 0.01, "batch_size": 32}
    with open(repo / "config.yaml", "w") as f:
        yaml.dump(config, f)
    
    # Create a Python file with argparse
    code = """
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--epochs', default=100)
parser.add_argument('--optimizer', default='adam')
"""
    with open(repo / "train.py", "w") as f:
        f.write(code)
    
    # Create a README
    with open(repo / "README.md", "w") as f:
        f.write("# My Model\nWe train for 100 epochs with a learning rate of 0.01.")
    
    return str(repo)

def test_drift_detection_logic(mock_repo):
    # Mock LLM response
    mock_claims = {
        "hyperparameters": {
            "epochs": 100,
            "learning_rate": 0.01,
            "batch_size": 64
        }
    }
    
    with patch("engine.configuration_drift_auditor._query_llm_for_claims", return_value=mock_claims):
        result, issues = audit_directory(mock_repo)
        
        assert isinstance(result, ConfigurationDriftResult)
        
        # Actual configs: epochs=50 (from yaml), learning_rate=0.01 (from yaml), 
        # batch_size=32 (from yaml), optimizer=adam (from argparse)
        assert result.actual_configs["epochs"] == 50
        assert result.actual_configs["learning_rate"] == 0.01
        assert result.actual_configs["batch_size"] == 32
        assert result.actual_configs["optimizer"] == "adam"
        
        # Drifts: 
        # epochs: claimed 100, actual 50 -> Drift
        # learning_rate: claimed 0.01, actual 0.01 -> No Drift
        # batch_size: claimed 64, actual 32 -> Drift
        
        drift_params = [d["parameter"] for d in result.drifts]
        assert "epochs" in drift_params
        assert "batch_size" in drift_params
        assert "learning_rate" not in drift_params
        
        assert len(issues) == 2
        assert any("epochs" in i.message for i in issues)
        assert any("batch_size" in i.message for i in issues)

def test_normalize_key():
    from engine.configuration_drift_auditor import _normalize_key
    assert _normalize_key("Learning Rate") == "learning_rate"
    assert _normalize_key("batch-size") == "batch_size"
    assert _normalize_key("EPOCHS") == "epochs"

def test_argparse_visitor():
    import ast
    from engine.configuration_drift_auditor import _ArgparseVisitor
    code = """
parser.add_argument('--lr', default=0.001)
parser.add_argument('--name', default='test')
parser.add_argument('--flag', action='store_true') # No default here
parser.add_argument('--neg', default=-1)
"""
    tree = ast.parse(code)
    visitor = _ArgparseVisitor()
    visitor.visit(tree)
    
    assert visitor.defaults["lr"] == 0.001
    assert visitor.defaults["name"] == "test"
    assert "flag" not in visitor.defaults
    assert visitor.defaults["neg"] == -1
