
import sys
import os
import json

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from engine.pipeline_auditor import audit_directory
from models import AuditReport

# Create a dummy repo structure to test
test_repo = 'scratch/test_repo'
os.makedirs(test_repo, exist_ok=True)
with open(os.path.join(test_repo, 'train.py'), 'w') as f:
    f.write("import pandas as pd\nimport torch\ndf = pd.read_csv('data.csv')\nmodel = torch.nn.Linear(10, 1)\n")

graph, issues = audit_directory(test_repo)
print(f"Nodes: {len(graph.nodes)}")
print(f"Edges: {len(graph.edges)}")
print(f"Completeness: {graph.completeness_score}")

report = AuditReport(
    categories=[],
    total_score=0,
    summary="test",
    pipeline_graph=graph
)

print("\nSerialized Report (pipeline_graph):")
print(json.dumps(report.model_dump()['pipeline_graph'], indent=2))
