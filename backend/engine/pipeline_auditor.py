"""
Pipeline Graph Reconstruction (PGR) module.
Automatically infers the ML workflow by analyzing AST patterns and data flow.
"""

from __future__ import annotations
import ast
import os
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Optional

from models import PipelineNode, PipelineEdge, PipelineGraph, Issue
from engine.import_graph import build_import_graph, ModuleInfo, ImportGraphResult
from engine.utils import skip_ignored_dirs, resolve_call_name

logger = logging.getLogger(__name__)

# Canonical ML Stages
STAGE_DATASET = "dataset"
STAGE_PREPROCESSING = "preprocessing"
STAGE_FEATURE_ENG = "feature_engineering"
STAGE_TRAINING = "training"
STAGE_EVALUATION = "evaluation"
STAGE_INFERENCE = "inference"
STAGE_ARTIFACT = "artifact"

STAGES = [
    STAGE_DATASET, STAGE_PREPROCESSING, STAGE_FEATURE_ENG,
    STAGE_TRAINING, STAGE_EVALUATION, STAGE_INFERENCE, STAGE_ARTIFACT
]

@dataclass
class StageSignal:
    stage: str
    framework: str
    patterns: List[str]  # Call names, Class names, or Var names
    weight: float = 1.0

# Detection Strategies
SIGNALS = [
    # Dataset Acquisition
    StageSignal(STAGE_DATASET, "pandas", ["read_csv", "read_parquet", "read_sql", "read_json", "read_excel", "read_feather"]),
    StageSignal(STAGE_DATASET, "torch", ["DataLoader", "datasets.LoadDataset", "torchvision.datasets", "Subset", "ConcatDataset"]),
    StageSignal(STAGE_DATASET, "tensorflow", ["tf.data.Dataset", "tf.keras.utils.get_file", "from_tensor_slices", "make_csv_dataset"]),
    StageSignal(STAGE_DATASET, "huggingface", ["load_dataset", "load_from_disk"]),
    StageSignal(STAGE_DATASET, "numpy", ["load", "loadtxt", "genfromtxt"]),
    
    # Preprocessing
    StageSignal(STAGE_PREPROCESSING, "sklearn", ["StandardScaler", "MinMaxScaler", "LabelEncoder", "OneHotEncoder", "ColumnTransformer", "SimpleImputer"]),
    StageSignal(STAGE_PREPROCESSING, "huggingface", ["AutoTokenizer", "Tokenizer", "encode", "batch_encode_plus", "feature_extractor"]),
    StageSignal(STAGE_PREPROCESSING, "torch", ["transforms.Compose", "transforms.Resize", "transforms.Normalize", "transforms.ToTensor"]),
    StageSignal(STAGE_PREPROCESSING, "opencv", ["cvtColor", "resize", "GaussianBlur", "imread"]),
    StageSignal(STAGE_PREPROCESSING, "nltk", ["tokenize", "stem", "word_tokenize"]),
    
    # Training
    StageSignal(STAGE_TRAINING, "torch", ["optimizer.step", "loss.backward", "model.train", "Trainer.train", "autograd.grad"]),
    StageSignal(STAGE_TRAINING, "tensorflow", ["model.fit", "GradientTape", "train_step", "model.train_on_batch"]),
    StageSignal(STAGE_TRAINING, "sklearn", ["LinearRegression.fit", "RandomForestClassifier.fit", "SVC.fit", "fit", "partial_fit"]),
    StageSignal(STAGE_TRAINING, "lightning", ["Trainer.fit", "training_step"]),
    StageSignal(STAGE_TRAINING, "xgboost", ["xgb.train", "XGBClassifier.fit", "XGBRegressor.fit"]),
    StageSignal(STAGE_TRAINING, "lightgbm", ["lgb.train", "LGBMClassifier.fit"]),
    
    # Evaluation
    StageSignal(STAGE_EVALUATION, "sklearn", ["accuracy_score", "f1_score", "classification_report", "confusion_matrix", "roc_auc_score", "mean_squared_error"]),
    StageSignal(STAGE_EVALUATION, "torch", ["model.eval", "torch.no_grad", "validate", "validation_step"]),
    StageSignal(STAGE_EVALUATION, "huggingface", ["evaluate", "compute_metrics", "eval_dataset"]),
    StageSignal(STAGE_EVALUATION, "tensorflow", ["model.evaluate", "test_step"]),
    
    # Artifact Generation
    StageSignal(STAGE_ARTIFACT, "torch", ["save", "save_state_dict"]),
    StageSignal(STAGE_ARTIFACT, "huggingface", ["save_pretrained", "push_to_hub", "save_model"]),
    StageSignal(STAGE_ARTIFACT, "pickle", ["dump"]),
    StageSignal(STAGE_ARTIFACT, "joblib", ["dump", "save"]),
    StageSignal(STAGE_ARTIFACT, "tensorflow", ["save_model", "model.save"]),
]

class DeepDataFlowTracker(ast.NodeVisitor):
    """
    Analyzes a single module for data flow between variables and function calls.
    Tracks which variables are outputs of which calls, and where they are used as inputs.
    """
    def __init__(self, module_name: str):
        self.module_name = module_name
        self.var_sources: Dict[str, str] = {}  # var_name -> source_call_name/stage
        self.call_dependencies: List[Dict[str, Any]] = [] # [{call: str, inputs: [str], outputs: [str], line: int}]

    def visit_Assign(self, node: ast.Assign):
        # Track: x = some_call()
        if isinstance(node.value, ast.Call):
            call_name = resolve_call_name(node.value)
            if call_name:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.var_sources[target.id] = call_name
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        call_name = resolve_call_name(node)
        if call_name:
            inputs = []
            for arg in node.args:
                if isinstance(arg, ast.Name) and arg.id in self.var_sources:
                    inputs.append(self.var_sources[arg.id])
            
            self.call_dependencies.append({
                "call": call_name,
                "inputs": inputs,
                "line": node.lineno
            })
        self.generic_visit(node)

class PipelineAuditor:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.nodes: Dict[str, PipelineNode] = {}
        self.edges: List[PipelineEdge] = []
        self.import_graph: ImportGraphResult = None

    def audit(self) -> PipelineGraph:
        # 1. Build import graph back-bone
        self.import_graph = build_import_graph(self.repo_path)
        
        # 2. Analyze each module for stage signals and data flow
        for mod_name, mod_info in self.import_graph.modules.items():
            self._analyze_module(mod_info)

        # 3. Connect nodes based on data flow and imports
        self._resolve_dependencies()

        # 4. Score completeness
        comp_score = self._compute_completeness()

        return PipelineGraph(
            nodes=list(self.nodes.values()),
            edges=self.edges,
            completeness_score=comp_score
        )

    def _analyze_module(self, info: ModuleInfo):
        # Detect stages by signals in calls
        detected_stages: Dict[str, List[Dict[str, Any]]] = {} # stage -> [{framework, call, line}]
        
        for call in info.calls_made:
            for sig in SIGNALS:
                for pattern in sig.patterns:
                    if pattern in call.name:
                        if sig.stage not in detected_stages:
                            detected_stages[sig.stage] = []
                        detected_stages[sig.stage].append({
                            "framework": sig.framework,
                            "call": call.name,
                            "line": call.line
                        })

        # Create nodes for detected stages
        for stage, findings in detected_stages.items():
            # Combine findings in same module into one node for simplicity in DAG
            node_id = f"{info.module_name}_{stage}"
            if node_id not in self.nodes:
                self.nodes[node_id] = PipelineNode(
                    id=node_id,
                    label=f"{stage.capitalize()} ({info.rel_path})",
                    stage=stage,
                    file=info.rel_path,
                    framework=findings[0]["framework"],
                    status="detected",
                    entry_function=findings[0]["call"]
                )

    def _resolve_dependencies(self):
        # Simple cross-module dependency: if A imports B, and B has a stage S1, A has a stage S2,
        # we check if A calls something from B in S2.
        
        # For now, let's use a simpler heuristic:
        # Dataset -> Preprocessing -> Training -> Evaluation -> Artifacts
        # If multiple stages exist in the repo, link them in this order if they share context.
        # Deep implementation: trace variable flow across modules (Future improvement)
        
        sorted_stages = STAGES
        
        # Group nodes by module
        mod_nodes: Dict[str, List[PipelineNode]] = {}
        for node in self.nodes.values():
            if node.file not in mod_nodes:
                mod_nodes[node.file] = []
            mod_nodes[node.file].append(node)

        # Intra-module edges (order by line number would be better but we combined findings)
        # Just follow the canonical sequence
        for file, nodes in mod_nodes.items():
            nodes.sort(key=lambda x: sorted_stages.index(x.stage))
            for i in range(len(nodes) - 1):
                self.edges.append(PipelineEdge(
                    source=nodes[i].id,
                    target=nodes[i+1].id,
                    type="execution_flow"
                ))

        # Inter-module edges based on imports
        for edge in self.import_graph.edges:
            src_nodes = [n for n in self.nodes.values() if n.file == self.import_graph.modules[edge.source].rel_path]
            tgt_nodes = [n for n in self.nodes.values() if n.file == self.import_graph.modules[edge.target].rel_path]
            
            for sn in src_nodes:
                for tn in tgt_nodes:
                    # If target is "upstream" in ML flow
                    if sorted_stages.index(tn.stage) < sorted_stages.index(sn.stage):
                        self.edges.append(PipelineEdge(
                            source=tn.id,
                            target=sn.id,
                            type="data_flow"
                        ))

    def _compute_completeness(self) -> float:
        present_stages = {n.stage for n in self.nodes.values()}
        required = {STAGE_DATASET, STAGE_TRAINING, STAGE_EVALUATION}
        
        if not required: return 100.0
        
        found = present_stages.intersection(required)
        return (len(found) / len(required)) * 100.0

def audit_directory(repo_path: str) -> tuple[PipelineGraph, list[Issue]]:
    auditor = PipelineAuditor(repo_path)
    graph = auditor.audit()
    
    issues = []
    # Generate issues based on missing stages
    present = {n.stage for n in graph.nodes}
    if STAGE_DATASET not in present:
        issues.append(Issue(
            rule="pipeline_completeness",
            severity="warning",
            message="No dataset ingestion stage detected. Repo may not be fully reproducible from scratch.",
            fix="Add data loading script (e.g., using pandas or torch.utils.data)."
        ))
    if STAGE_TRAINING not in present:
        issues.append(Issue(
            rule="pipeline_completeness",
            severity="warning",
            message="No training loop detected.",
            fix="Implement a training script with framework-specific optimization loops."
        ))
    if STAGE_EVALUATION not in present:
        issues.append(Issue(
            rule="pipeline_completeness",
            severity="critical",
            message="No evaluation stage detected. Claimed results cannot be verified.",
            fix="Add evaluation scripts and metric reporting."
        ))

    return graph, issues
