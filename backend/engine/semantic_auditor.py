"""
Semantic documentation audit using LLM.

Parses README.md to extract claimed file paths, scripts, and commands,
then verifies them against the actual repository structure.
"""

from __future__ import annotations
import json
import os
import logging
import re
from dataclasses import dataclass, field

try:
    from openai import OpenAI
except ModuleNotFoundError:
    class OpenAI:
        def __init__(self, *args, **kwargs):
            raise ImportError('openai package is required for LLM functionality')
from config import get_settings
from models import Issue
from engine.utils import skip_ignored_dirs

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a precise technical auditor. Analyze the following README content from \
a machine learning research repository and extract structured information.

Return ONLY valid JSON with this exact schema:
{
  "claimed_files": ["list of file paths mentioned as existing in the repo"],
  "claimed_commands": ["list of shell commands the user is told to run"],
  "claimed_data_dirs": ["list of data directories referenced"],
  "sections_present": {
    "installation": true/false,
    "usage": true/false,
    "datasets": true/false,
    "training": true/false,
    "evaluation": true/false
  }
}

Rules:
- Only extract concrete file/directory paths, not abstract descriptions.
- For commands, extract the full command line.
- sections_present should check for the presence of those topics, \
even if the heading is named differently.
- If a section is absent, set it to false.
"""


@dataclass
class SemanticAuditResult:
    has_readme: bool = False
    readme_format: str = ""
    claimed_files: list[str] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    claimed_commands: list[str] = field(default_factory=list)
    claimed_data_dirs: list[str] = field(default_factory=list)
    missing_data_dirs: list[str] = field(default_factory=list)
    sections_present: dict[str, bool] = field(default_factory=dict)
    llm_error: str | None = None


def _find_readme(repo_path: str) -> tuple[str | None, str]:
    """Find README file, returns (path, format)."""
    candidates = [
        ("README.md", "markdown"),
        ("readme.md", "markdown"),
        ("README.rst", "restructuredtext"),
        ("README.txt", "plaintext"),
        ("README", "plaintext"),
    ]
    for fname, fmt in candidates:
        fpath = os.path.join(repo_path, fname)
        if os.path.isfile(fpath):
            return fpath, fmt
    return None, ""


def _read_readme(path: str, max_chars: int = 15000) -> str:
    """Read README content, truncating if needed."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(max_chars)
        return content
    except OSError:
        return ""


def _get_repo_file_listing(repo_path: str) -> set[str]:
    """Get a set of all relative file/dir paths in the repo."""
    paths: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(repo_path):
        skip_ignored_dirs(dirnames)
        rel_dir = os.path.relpath(dirpath, repo_path)
        if rel_dir != ".":
            paths.add(rel_dir)
        for fname in filenames:
            if not fname.startswith("."):
                paths.add(os.path.join(rel_dir, fname).lstrip("./"))
    return paths


def _query_llm(readme_content: str) -> dict:
    """Query Groq LLM to extract structured info from README."""
    settings = get_settings()
    if not settings.hf_api_key:
        raise RuntimeError("HF_API_KEY is not configured")

    client = OpenAI(
        base_url="https://router.huggingface.co/v1/",
        api_key=settings.hf_api_key
    )

    response = client.chat.completions.create(
        model="meta-llama/Llama-3.3-70B-Instruct",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": readme_content},
        ],
        temperature=0.0,
        max_tokens=2000,
        response_format={"type": "json_object"},
        timeout=120,
    )

    raw = response.choices[0].message.content
    if not raw:
        raise ValueError("LLM returned empty response")

    return json.loads(raw)


def _safe_parse_llm_response(data: dict) -> dict:
    """Validate and normalize the LLM response structure."""
    result = {
        "claimed_files": [],
        "claimed_commands": [],
        "claimed_data_dirs": [],
        "sections_present": {
            "installation": False,
            "usage": False,
            "datasets": False,
            "training": False,
            "evaluation": False,
        },
    }

    if isinstance(data.get("claimed_files"), list):
        result["claimed_files"] = [
            str(f) for f in data["claimed_files"] if isinstance(f, str)
        ]
    if isinstance(data.get("claimed_commands"), list):
        result["claimed_commands"] = [
            str(c) for c in data["claimed_commands"] if isinstance(c, str)
        ]
    if isinstance(data.get("claimed_data_dirs"), list):
        result["claimed_data_dirs"] = [
            str(d) for d in data["claimed_data_dirs"] if isinstance(d, str)
        ]
    if isinstance(data.get("sections_present"), dict):
        for key in result["sections_present"]:
            if key in data["sections_present"]:
                result["sections_present"][key] = bool(
                    data["sections_present"][key]
                )

    return result


def audit_directory(repo_path: str) -> tuple[SemanticAuditResult, list[Issue]]:
    """Perform semantic audit of README vs repository structure."""
    result = SemanticAuditResult()
    issues: list[Issue] = []

    # Find README
    readme_path, readme_fmt = _find_readme(repo_path)
    if not readme_path:
        result.has_readme = False
        issues.append(Issue(
            rule="documentation",
            severity="critical",
            message="No README file found in repository root.",
            fix="Add a README.md documenting installation, usage, and datasets.",
        ))
        return result, issues

    result.has_readme = True
    result.readme_format = readme_fmt
    readme_content = _read_readme(readme_path)

    if len(readme_content.strip()) < 50:
        issues.append(Issue(
            rule="documentation",
            severity="warning",
            file="README.md",
            message="README exists but is very short (< 50 characters).",
            fix="Expand README to include installation, usage, and dataset sections.",
        ))
        return result, issues

    # Query LLM for structured analysis
    try:
        raw_data = _query_llm(readme_content)
        parsed = _safe_parse_llm_response(raw_data)
    except Exception as e:
        logger.error("LLM query failed: %s", e)
        result.llm_error = str(e)
        # Fallback: basic regex checks on README
        return _fallback_audit(repo_path, readme_content, result, issues)

    # Verify claimed files exist
    repo_files = _get_repo_file_listing(repo_path)
    result.claimed_files = parsed["claimed_files"]
    result.claimed_commands = parsed["claimed_commands"]
    for claimed in parsed["claimed_files"]:
        # Normalize the path
        normalized = claimed.lstrip("./")
        if normalized and normalized not in repo_files:
            # Check with common variations
            found = False
            for variant in [normalized, normalized.lower()]:
                if variant in repo_files:
                    found = True
                    break
            if not found:
                result.missing_files.append(claimed)
                issues.append(Issue(
                    rule="semantic",
                    severity="warning",
                    file="README.md",
                    message=(
                        f"README references `{claimed}` but it does not exist "
                        f"in the repository."
                    ),
                    fix=f"Update README or add the missing file: `{claimed}`.",
                ))

    # Verify data directories
    result.claimed_data_dirs = parsed["claimed_data_dirs"]
    for ddir in parsed["claimed_data_dirs"]:
        normalized = ddir.lstrip("./")
        if normalized and normalized not in repo_files:
            result.missing_data_dirs.append(ddir)
            issues.append(Issue(
                rule="semantic",
                severity="warning",
                file="README.md",
                message=(
                    f"README references data directory `{ddir}` but it does "
                    f"not exist."
                ),
                fix=(
                    f"Create `{ddir}/` or update README with correct data paths."
                ),
            ))

    # Check documentation sections
    result.sections_present = parsed["sections_present"]
    required_sections = ["installation", "usage", "datasets"]
    for section in required_sections:
        if not result.sections_present.get(section, False):
            issues.append(Issue(
                rule="documentation",
                severity="warning",
                file="README.md",
                message=f"README is missing a '{section}' section.",
                fix=f"Add a '{section.title()}' section to README.md.",
            ))

    return result, issues


def _fallback_audit(
    repo_path: str,
    readme_content: str,
    result: SemanticAuditResult,
    issues: list[Issue],
) -> tuple[SemanticAuditResult, list[Issue]]:
    """Basic regex-based README audit when LLM is unavailable."""
    content_lower = readme_content.lower()

    sections = {
        "installation": bool(re.search(r"#.*install", content_lower)),
        "usage": bool(re.search(r"#.*(usage|how to|getting started)", content_lower)),
        "datasets": bool(re.search(r"#.*(data|dataset)", content_lower)),
        "training": bool(re.search(r"#.*(train|training)", content_lower)),
        "evaluation": bool(re.search(r"#.*(eval|evaluation|test)", content_lower)),
    }
    result.sections_present = sections

    for section in ["installation", "usage", "datasets"]:
        if not sections.get(section):
            issues.append(Issue(
                rule="documentation",
                severity="warning",
                file="README.md",
                message=f"README appears to be missing a '{section}' section.",
                fix=f"Add a '{section.title()}' section to README.md.",
            ))

    issues.append(Issue(
        rule="semantic",
        severity="info",
        message=(
            "AI semantic audit unavailable — performed basic regex analysis. "
            f"Reason: {result.llm_error}"
        ),
    ))

    return result, issues