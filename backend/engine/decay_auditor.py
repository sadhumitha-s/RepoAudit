"""
Reproducibility Decay Tracking (Temporal Analysis).

Tracks how a repository's reproducibility score degrades over time as dependencies go stale.
Detects yanked packages, CVEs, and estimates "shelf life" and "time-to-break" for dependencies.
"""

from __future__ import annotations
import os
import re
import logging
from dataclasses import dataclass, field
import urllib.request
import json
from datetime import datetime, timezone

from models import Issue

logger = logging.getLogger(__name__)

@dataclass
class DecayAuditResult:
    yanked_packages: dict[str, str] = field(default_factory=dict)
    cve_packages: dict[str, list[str]] = field(default_factory=dict)
    avg_package_age_days: int = 0
    shelf_life_days: int = 1825  # defaults to 5 years
    time_to_break_days: int = 1825
    decay_curve: list[dict[str, float]] = field(default_factory=list)


def _parse_pinned_requirements(filepath: str) -> dict[str, str]:
    pinned = {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return pinned

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # match pinning: package==version, package>=version, package~=version
        match = re.match(r"^([A-Za-z0-9_.\-]+)(?:==|>=|~=)([A-Za-z0-9_.\-]+)", line)
        if match:
            pkg = match.group(1).lower().replace("-", "_")
            ver = match.group(2)
            pinned[pkg] = ver
    return pinned


def _fetch_pypi_info(pkg: str, ver: str) -> dict | None:
    url = f"https://pypi.org/pypi/{pkg}/{ver}/json"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'RepoAudit/1.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        logger.warning(f"Failed to fetch PyPI info for {pkg}=={ver}: {e}")
    return None


def audit_directory(repo_path: str) -> tuple[DecayAuditResult, list[Issue]]:
    """Audit for decay (yanked packages, CVEs, bitrot)."""
    result = DecayAuditResult()
    issues: list[Issue] = []

    req_path = os.path.join(repo_path, "requirements.txt")
    if not os.path.isfile(req_path):
        return result, issues

    pinned_deps = _parse_pinned_requirements(req_path)
    if not pinned_deps:
        return result, issues

    total_age_days = 0
    now = datetime.now(timezone.utc)
    valid_ages = 0

    for pkg, ver in pinned_deps.items():
        info = _fetch_pypi_info(pkg, ver)
        if not info:
            continue
        
        info_data = info.get("info", {})
        
        # Check if yanked
        if info_data.get("yanked"):
            reason = info_data.get("yanked_reason") or "No reason provided"
            result.yanked_packages[pkg] = ver
            issues.append(Issue(
                rule="decay",
                severity="critical",
                file="requirements.txt",
                message=f"Dependency {pkg}=={ver} has been yanked from PyPI. Reason: {reason}",
                fix=f"Update {pkg} to a newer, unyanked version."
            ))

        # Check for CVEs
        vulns = info.get("vulnerabilities", [])
        if vulns:
            cve_ids = [v.get("id", "Unknown") for v in vulns]
            result.cve_packages[pkg] = cve_ids
            issues.append(Issue(
                rule="decay",
                severity="warning",
                file="requirements.txt",
                message=f"Dependency {pkg}=={ver} has known CVEs: {', '.join(cve_ids)}",
                fix=f"Update {pkg} to a patched version."
            ))

        # Calculate Age
        urls = info.get("urls", [])
        if urls and len(urls) > 0:
            upload_time_str = urls[0].get("upload_time_iso_8601")
            if upload_time_str:
                try:
                    upload_time = datetime.fromisoformat(upload_time_str.replace("Z", "+00:00"))
                    age_days = (now - upload_time).days
                    total_age_days += age_days
                    valid_ages += 1
                except ValueError:
                    pass

    if valid_ages > 0:
        avg_age = total_age_days // valid_ages
        result.avg_package_age_days = avg_age
        
        # Shelf life: starts at 5 years (1825 days), reduced by average age
        result.shelf_life_days = max(0, 1825 - avg_age)
        
        # Time to break: shorter if there are yanked/CVE pkgs
        penalty = (len(result.yanked_packages) * 365) + (len(result.cve_packages) * 180)
        result.time_to_break_days = max(0, result.shelf_life_days - penalty)
        
        # Generate decay curve (last 5 years, points every year)
        base_score = 100 - (len(result.yanked_packages) * 20) - (len(result.cve_packages) * 10)
        
        for year in range(5):
            year_ago = 4 - year
            # score decays as packages age backwards in time
            score_est = max(0, base_score - ((avg_age - (year_ago * 365)) / 365 * 10))
            result.decay_curve.append({
                "date": f"Year -{year_ago}" if year_ago > 0 else "Current", 
                "score": round(min(100, max(0, score_est)), 1)
            })
    else:
        # Default curve if no age data
        for year in range(5):
            year_ago = 4 - year
            result.decay_curve.append({
                "date": f"Year -{year_ago}" if year_ago > 0 else "Current",
                "score": 100.0
            })

    return result, issues
