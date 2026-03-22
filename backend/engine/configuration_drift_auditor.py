"""
Configuration Drift Detection.

Catch discrepancies between claimed hyperparameters in README and actual values
found in config files (YAML, JSON) or argparse defaults in Python code.
"""

from __future__ import annotations
import ast
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

import yaml
from openai import OpenAI
from config import get_settings
from models import Issue

logger = logging.getLogger(__name__)

_DRIFT_PROMPT = """\
You are a precise technical auditor. Analyze the following README content from \
a machine learning research repository and extract claimed hyperparameters or configuration values (e.g., epochs, learning rate, batch size).

Return ONLY valid JSON with this exact schema:
{
  "hyperparameters": {
    "parameter_name": "claimed_value"
  }
}

Rules:
- Focus on training/evaluation parameters like epochs, learning rate, batch size, optimizer, etc.
- Only extract concrete values mentioned.
- parameter_name should be lowercased and use underscores (e.g., "learning_rate", "batch_size", "epochs").
- If no hyperparameters are found, return an empty object for hyperparameters.
"""

@dataclass
class ConfigurationDriftResult:
    actual_configs: dict[str, Any] = field(default_factory=dict)
    claimed_configs: dict[str, Any] = field(default_factory=dict)
    drifts: list[dict[str, Any]] = field(default_factory=list)
    llm_error: str | None = None

class _ArgparseVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.defaults: dict[str, Any] = {}

    def visit_Call(self, node: ast.Call) -> None:
        # Detect parser.add_argument('--name', default=VALUE)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument":
            arg_name = None
            default_val = None
            
            # Get the argument name from positional args
            if node.args:
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                    arg_name = first_arg.value.lstrip("-").replace("-", "_")
            
            # Get the default value from keywords
            for kw in node.keywords:
                if kw.arg == "default":
                    if isinstance(kw.value, ast.Constant):
                        default_val = kw.value.value
                    elif isinstance(kw.value, ast.UnaryOp) and isinstance(kw.value.operand, ast.Constant):
                        # Handle negative numbers
                        if isinstance(kw.value.op, ast.USub):
                            default_val = -kw.value.operand.value
                    break
            
            if arg_name and default_val is not None:
                self.defaults[arg_name] = default_val
        
        self.generic_visit(node)

def _parse_config_file(filepath: str) -> dict[str, Any]:
    """Parse YAML or JSON config files."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            if filepath.endswith((".yaml", ".yml")):
                # Use SafeLoader
                data = yaml.load(f, Loader=yaml.SafeLoader)
                return data if isinstance(data, dict) else {}
            elif filepath.endswith(".json"):
                data = json.load(f)
                return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning("Failed to parse config file %s: %s", filepath, e)
    return {}

def _extract_argparse_defaults(repo_path: str) -> dict[str, Any]:
    """Search for argparse defaults in Python files."""
    all_defaults: dict[str, Any] = {}
    for dirpath, dirnames, filenames in os.walk(repo_path):
        # Skip common directories
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in ("venv", ".venv", "env", "node_modules", "__pycache__")]
        for fname in filenames:
            if fname.endswith(".py"):
                fpath = os.path.join(dirpath, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        tree = ast.parse(f.read(), filename=fpath)
                        visitor = _ArgparseVisitor()
                        visitor.visit(tree)
                        all_defaults.update(visitor.defaults)
                except Exception:
                    continue
    return all_defaults

def _query_llm_for_claims(readme_content: str) -> dict:
    """Query LLM to extract hyperparameter claims from README."""
    settings = get_settings()
    if not settings.hf_api_key:
        return {"hyperparameters": {}}

    client = OpenAI(
        base_url="https://api-inference.huggingface.co/v1/",
        api_key=settings.hf_api_key
    )

    try:
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct",
            messages=[
                {"role": "system", "content": _DRIFT_PROMPT},
                {"role": "user", "content": readme_content},
            ],
            temperature=0.0,
            max_tokens=1000,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        if not raw:
            return {"hyperparameters": {}}
        return json.loads(raw)
    except Exception as e:
        logger.error("LLM query for drift detection failed: %s", e)
        return {"hyperparameters": {}, "error": str(e)}

def _normalize_key(key: str) -> str:
    """Normalize hyperparameter key for comparison."""
    return key.lower().replace("-", "_").replace(" ", "_")

def audit_directory(repo_path: str) -> tuple[ConfigurationDriftResult, list[Issue]]:
    result = ConfigurationDriftResult()
    issues: list[Issue] = []

    # 1. Find and parse config files
    config_exts = (".yaml", ".yml", ".json")
    for dirpath, dirnames, filenames in os.walk(repo_path):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in ("venv", ".venv", "env", "node_modules", "__pycache__")]
        for fname in filenames:
            if fname.endswith(config_exts):
                fpath = os.path.join(dirpath, fname)
                config_data = _parse_config_file(fpath)
                for k, v in config_data.items():
                    norm_k = _normalize_key(k)
                    # Simple heuristic: if value is basic (int, float, str, bool), store it
                    if isinstance(v, (int, float, str, bool)):
                        result.actual_configs[norm_k] = v

    # 2. Extract argparse defaults
    argparse_defaults = _extract_argparse_defaults(repo_path)
    for k, v in argparse_defaults.items():
        norm_k = _normalize_key(k)
        # Config files take precedence over code defaults
        if norm_k not in result.actual_configs:
            result.actual_configs[norm_k] = v

    # 3. Extract claims from README
    readme_path = None
    for fname in ["README.md", "readme.md", "README.rst"]:
        fpath = os.path.join(repo_path, fname)
        if os.path.isfile(fpath):
            readme_path = fpath
            break
    
    if not readme_path:
        return result, issues

    try:
        with open(readme_path, "r", encoding="utf-8", errors="replace") as f:
            readme_content = f.read(15000)
    except OSError:
        return result, issues

    claims_data = _query_llm_for_claims(readme_content)
    result.llm_error = claims_data.get("error")
    claimed_hparams = claims_data.get("hyperparameters", {})
    
    for k, v in claimed_hparams.items():
        norm_k = _normalize_key(k)
        result.claimed_configs[norm_k] = v

    # 4. Compare actual vs claimed
    for k, claimed_v in result.claimed_configs.items():
        if k in result.actual_configs:
            actual_v = result.actual_configs[k]
            
            # Simple soft comparison
            match = False
            try:
                # Try to convert to float for numeric comparison
                if str(claimed_v).strip() == str(actual_v).strip():
                    match = True
                elif float(claimed_v) == float(actual_v):
                    match = True
            except (ValueError, TypeError):
                pass
            
            if not match:
                result.drifts.append({
                    "parameter": k,
                    "claimed": claimed_v,
                    "actual": actual_v
                })
                issues.append(Issue(
                    rule="semantic",
                    severity="warning",
                    file="README.md",
                    message=(
                        f"Configuration drift detected for `{k}`: "
                        f"README says `{claimed_v}` but config/code uses `{actual_v}`."
                    ),
                    fix=f"Update README or config files to ensure hyperparameters match."
                ))

    return result, issues
