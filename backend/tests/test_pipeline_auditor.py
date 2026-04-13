import pytest
import os
import shutil
import tempfile
from engine.pipeline_auditor import audit_directory, STAGE_TRAINING, STAGE_DATASET, STAGE_EVALUATION

@pytest.fixture
def mock_repo():
    """Create a temporary directory with mock ML code files."""
    tmpdir = tempfile.mkdtemp()
    
    # 1. Dataset loading file
    with open(os.path.join(tmpdir, "data.py"), "w") as f:
        f.write("import pandas as pd\n")
        f.write("def load():\n")
        f.write("    return pd.read_csv('data.csv')\n")
        
    # 2. Preprocessing file
    with open(os.path.join(tmpdir, "preprocess.py"), "w") as f:
        f.write("from sklearn.preprocessing import StandardScaler\n")
        f.write("def clean(df):\n")
        f.write("    scaler = StandardScaler()\n")
        f.write("    return scaler.fit_transform(df)\n")

    # 3. Training file (Entry point)
    with open(os.path.join(tmpdir, "train.py"), "w") as f:
        f.write("import torch\n")
        f.write("from data import load\n")
        f.write("from preprocess import clean\n")
        f.write("def train():\n")
        f.write("    data = load()\n")
        f.write("    cleaned = clean(data)\n")
        f.write("    model = torch.nn.Linear(10, 1)\n")
        f.write("    opt = torch.optim.SGD(model.parameters(), lr=0.01)\n")
        f.write("    # Mock training loop\n")
        f.write("    opt.step()\n")
        f.write("    torch.save(model.state_dict(), 'model.pt')\n")
        f.write("if __name__ == '__main__':\n")
        f.write("    train()\n")

    yield tmpdir
    shutil.rmtree(tmpdir)

def test_pipeline_reconstruction(mock_repo):
    graph, issues = audit_directory(mock_repo)
    
    # Assert nodes exist for major stages
    stages = {n.stage for n in graph.nodes}
    assert STAGE_DATASET in stages
    assert STAGE_TRAINING in stages
    # Note: STAGE_EVALUATION might be missing in this mock, which is good to test issues
    
    # Check edges
    assert len(graph.edges) > 0
    
    # Check completeness score
    # Found: Dataset, Training. Missing: Evaluation. -> 2/3 = 66.6%
    assert 66.0 <= graph.completeness_score <= 67.0

def test_missing_stages_issues(mock_repo):
    # The mock_repo doesn't have an evaluation stage
    graph, issues = audit_directory(mock_repo)
    
    eval_issues = [i for i in issues if "evaluation" in i.message.lower()]
    assert len(eval_issues) > 0
    assert eval_issues[0].severity == "critical"

def test_framework_detection(mock_repo):
    graph, _ = audit_directory(mock_repo)
    
    torch_nodes = [n for n in graph.nodes if n.framework == "torch"]
    pandas_nodes = [n for n in graph.nodes if n.framework == "pandas"]
    
    assert len(torch_nodes) > 0
    assert len(pandas_nodes) > 0
