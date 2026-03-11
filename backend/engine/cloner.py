from __future__ import annotations
import os
import shutil
import subprocess
import tempfile
import re
import logging

from config import get_settings

logger = logging.getLogger(__name__)

_SAFE_REPO_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")


def _parse_owner_repo(url: str) -> tuple[str, str]:
    """Extract owner and repo name from a GitHub URL."""
    parts = url.rstrip("/").split("/")
    if len(parts) < 2:
        raise ValueError(f"Cannot parse owner/repo from URL: {url}")
    owner, repo = parts[-2], parts[-1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not _SAFE_REPO_RE.match(owner) or not _SAFE_REPO_RE.match(repo):
        raise ValueError(f"Invalid owner or repo name: {owner}/{repo}")
    return owner, repo


def resolve_commit_hash(url: str) -> str:
    """Resolve the latest commit hash for a repository without cloning."""
    result = subprocess.run(
        ["git", "ls-remote", url, "HEAD"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "not found" in stderr.lower() or "repository" in stderr.lower():
            raise ValueError(f"Repository not found or not accessible: {url}")
        raise RuntimeError(f"Failed to resolve commit hash: {stderr}")

    output = result.stdout.strip()
    if not output:
        raise ValueError(f"Empty repository or no HEAD ref: {url}")

    commit_hash = output.split()[0]
    if not re.match(r"^[0-9a-f]{40}$", commit_hash):
        raise ValueError(f"Invalid commit hash format: {commit_hash}")
    return commit_hash


def clone_repo(url: str) -> tuple[str, str, str]:
    """
    Shallow-clone a public GitHub repo. Returns (clone_path, owner, repo_name).
    Raises on private repos, oversized repos, or network failures.
    """
    settings = get_settings()
    owner, repo = _parse_owner_repo(url)

    base = settings.clone_base_dir
    os.makedirs(base, exist_ok=True)

    clone_dir = tempfile.mkdtemp(prefix=f"{owner}_{repo}_", dir=base)

    try:
        result = subprocess.run(
            [
                "git", "clone",
                "--depth", "1",
                "--single-branch",
                url,
                clone_dir,
            ],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "Authentication" in stderr or "could not read" in stderr:
                raise PermissionError(
                    f"Repository requires authentication (private?): {url}"
                )
            raise RuntimeError(f"Git clone failed: {stderr}")

        # Check size
        total_size = _get_dir_size_mb(clone_dir)
        if total_size > settings.max_repo_size_mb:
            raise ValueError(
                f"Repository size ({total_size:.1f}MB) exceeds "
                f"limit ({settings.max_repo_size_mb}MB)"
            )

        return clone_dir, owner, repo

    except Exception:
        cleanup_clone(clone_dir)
        raise


def cleanup_clone(clone_path: str) -> None:
    """Safely remove a cloned repository directory."""
    if not clone_path:
        return
    settings = get_settings()
    real_path = os.path.realpath(clone_path)
    real_base = os.path.realpath(settings.clone_base_dir)
    # Guard: only delete within the designated clone directory
    if not real_path.startswith(real_base):
        logger.warning(
            "Refusing to delete path outside clone base: %s", clone_path
        )
        return
    shutil.rmtree(clone_path, ignore_errors=True)


def _get_dir_size_mb(path: str) -> float:
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.isfile(fp) and not os.path.islink(fp):
                total += os.path.getsize(fp)
    return total / (1024 * 1024)