from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


API_URL = env("INPUT_API_URL").rstrip("/")
REPO_URL = env("INPUT_REPO_URL")
THRESHOLD = int(env("INPUT_THRESHOLD", "0"))
REQUEST_TIMEOUT_SECONDS = int(env("INPUT_REQUEST_TIMEOUT_SECONDS", "180"))
REQUEST_RETRIES = int(env("INPUT_REQUEST_RETRIES", "4"))
TIMEOUT_SECONDS = int(env("INPUT_TIMEOUT_SECONDS", "420"))
POLL_INTERVAL_SECONDS = int(env("INPUT_POLL_INTERVAL_SECONDS", "5"))
GITHUB_REPOSITORY = env("GITHUB_REPOSITORY")
GITHUB_OUTPUT = env("GITHUB_OUTPUT")
GITHUB_STEP_SUMMARY = env("GITHUB_STEP_SUMMARY")


def log(msg: str) -> None:
    print(msg, flush=True)


def fail(msg: str, code: int = 1) -> None:
    print(f"::error::{msg}", flush=True)
    sys.exit(code)


def set_output(name: str, value: str) -> None:
    if not GITHUB_OUTPUT:
        return
    with open(GITHUB_OUTPUT, "a", encoding="utf-8") as f:
        f.write(f"{name}<<EOF\n{value}\nEOF\n")


def append_summary(markdown: str) -> None:
    if not GITHUB_STEP_SUMMARY:
        return
    with open(GITHUB_STEP_SUMMARY, "a", encoding="utf-8") as f:
        f.write(markdown)
        if not markdown.endswith("\n"):
            f.write("\n")


def request_json(method: str, url: str, body: dict | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    last_err = None
    for attempt in range(REQUEST_RETRIES + 1):
        req = urllib.request.Request(url=url, method=method, headers=headers, data=data)
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", errors="ignore")
            detail = text
            try:
                payload = json.loads(text)
                detail = payload.get("detail", text)
            except Exception:
                pass
            # Retry transient gateway/service errors
            if e.code in (502, 503, 504) and attempt < REQUEST_RETRIES:
                sleep_s = min(30, 2 ** attempt)
                log(f"Transient HTTP {e.code}, retrying in {sleep_s}s...")
                time.sleep(sleep_s)
                last_err = f"HTTP {e.code}: {detail}"
                continue
            fail(f"HTTP {e.code} calling {url}: {detail}")
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = str(getattr(e, "reason", e))
            if attempt < REQUEST_RETRIES:
                sleep_s = min(30, 2 ** attempt)
                log(f"Network timeout/error, retrying in {sleep_s}s... ({last_err})")
                time.sleep(sleep_s)
                continue
            fail(f"Network error calling {url}: {last_err}")

    fail(f"Request failed after retries: {last_err}")
    return {}


def sanitize_repo_url(url: str) -> str:
    return url.rstrip("/")


def infer_repo_url() -> str:
    if REPO_URL:
        return sanitize_repo_url(REPO_URL)
    if not GITHUB_REPOSITORY:
        fail("No repo-url input provided and GITHUB_REPOSITORY is missing.")
    return f"https://github.com/{GITHUB_REPOSITORY}"


def short_sha(commit_hash: str | None) -> str:
    if not commit_hash:
        return ""
    return commit_hash[:7]


def summarize_issues(report: dict) -> tuple[int, int, int]:
    critical = 0
    warning = 0
    info = 0
    for category in report.get("categories", []):
        for issue in category.get("issues", []):
            sev = issue.get("severity", "")
            if sev == "critical":
                critical += 1
            elif sev == "warning":
                warning += 1
            elif sev == "info":
                info += 1
    return critical, warning, info


def build_summary(result: dict) -> str:
    report = result.get("report") or {}
    score = float(result.get("score") or 0)
    status = result.get("status", "unknown")
    commit = short_sha(result.get("commit_hash"))
    summary = report.get("summary", "").strip()
    categories = report.get("categories", [])
    critical, warning, info_count = summarize_issues(report)

    lines: list[str] = []
    lines.append("## RepoAudit Result")
    lines.append("")
    lines.append(f"- Status: **{status}**")
    lines.append(f"- Score: **{score:.1f}/100**")
    if commit:
        lines.append(f"- Commit: **{commit}**")
    lines.append(f"- Issues: **critical {critical}**, **warning {warning}**, **info {info_count}**")
    lines.append("")

    if summary:
        lines.append(f"> {summary}")
        lines.append("")

    if categories:
        lines.append("### Category Scores")
        lines.append("")
        lines.append("| Category | Weight | Score |")
        lines.append("|---|---:|---:|")
        for c in categories:
            name = c.get("name", "unknown")
            weight = float(c.get("weight", 0)) * 100
            cscore = float(c.get("score", 0))
            lines.append(f"| {name} | {weight:.0f}% | {cscore:.1f} |")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    if not API_URL:
        fail("Missing required input: api-url")

    repo_url = infer_repo_url()
    log(f"Using API: {API_URL}")
    log(f"Auditing repo: {repo_url}")

    log("Warming up backend...")
    request_json("GET", f"{API_URL}/health")

    submit_url = f"{API_URL}/api/v1/audit"
    submit_resp = request_json("POST", submit_url, {"url": repo_url})

    audit_id = submit_resp.get("audit_id")
    if not audit_id:
        fail("Backend did not return audit_id")

    status = submit_resp.get("status", "unknown")
    log(f"Audit ID: {audit_id}, initial status: {status}")

    terminal = {"completed", "failed"}
    deadline = time.time() + TIMEOUT_SECONDS

    while status not in terminal and time.time() < deadline:
        time.sleep(POLL_INTERVAL_SECONDS)
        status_url = f"{API_URL}/api/v1/audit/{urllib.parse.quote(str(audit_id))}/status"
        status_resp = request_json("GET", status_url)
        status = status_resp.get("status", "unknown")
        progress = status_resp.get("progress", "")
        log(f"Status: {status} | {progress}")

    if status not in terminal:
        fail(f"Timed out after {TIMEOUT_SECONDS}s waiting for audit completion")

    get_url = f"{API_URL}/api/v1/audit/{urllib.parse.quote(str(audit_id))}"
    result = request_json("GET", get_url)

    final_status = result.get("status", status)
    score_val = float(result.get("score") or 0)
    report = result.get("report") or {}

    set_output("audit-id", str(audit_id))
    set_output("status", str(final_status))
    set_output("score", f"{score_val:.1f}")
    set_output("report-json", json.dumps(report, separators=(",", ":")))

    append_summary(build_summary(result))

    if final_status != "completed":
        fail(f"Audit finished with status {final_status}")

    if THRESHOLD > 0 and score_val < THRESHOLD:
        fail(
            f"Score {score_val:.1f} is below threshold {THRESHOLD}. "
            f"Set threshold to 0 to disable gating."
        )

    log("RepoAudit action completed successfully.")


if __name__ == "__main__":
    main()