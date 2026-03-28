# GitHub Action Usage Guide

The **RepoAudit GitHub Action** is a powerful way to integrate reproducibility checks directly into your CI/CD pipeline. It allows you to automatically audit pull requests and fail the build if a reproducibility threshold is not met.

## 1. Quick Start

Add a new workflow file (e.g., `.github/workflows/reproducibility.yml`) to your repository.

```yaml
name: Reproducibility Check
on:
  pull_request:
    branches: [main]

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run RepoAudit
        uses: sadhumitha-s/RepoAudit@v1.0.0
        with:
          api-url: https://repoaudit-api.onrender.com
          threshold: "70" # Fail if score is below 70
```

## 2. Configuration Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `api-url` | Yes | — | Base URL of the RepoAudit API. |
| `repo-url` | No | Current repo | Override the repository URL to audit. |
| `threshold` | No | `0` | Minimum score (0-100) to pass the build. |
| `timeout-seconds` | No | `600` | Max total wait time for the audit to complete. |
| `poll-interval-seconds` | No | `5` | Interval in seconds between status updates. |
| `request-timeout-seconds`| No | `180` | Per HTTP request timeout. |
| `request-retries` | No | `4` | Retries for transient network/gateway failures. |

## 3. Action Outputs

You can use the outputs of the action in subsequent steps:

| Output | Description |
|--------|-------------|
| `score` | Numerical reproducibility score (0–100). |
| `audit-id` | Unique ID for the completed audit. |
| `status` | `completed` or `failed`. |
| `report-json` | Full audit report in JSON format. |

### Example Usage of Outputs:
```yaml
      - run: echo "Repository Score: ${{ steps.audit.outputs.score }}/100"
      - run: echo "Detailed Report: https://repo-audit.vercel.app/audit/${{ steps.audit.outputs.audit-id }}"
```

## 4. Advanced Scenarios

### Auditing External Repositories (Research Benchmarks)
You can use the action in a centralized monitoring repo to audit a list of third-party repositories.

```yaml
      - name: Audit Reference ML Repo
        uses: sadhumitha-s/RepoAudit@v1.0.0
        with:
          api-url: https://repoaudit-api.onrender.com
          repo-url: "https://github.com/facebookresearch/llama"
```

### Custom Retries and Timeouts
For large repositories with complex reproduction scripts (high-level replay verification), you may need to increase the default timeout.

```yaml
      - name: Long-running Audit
        uses: sadhumitha-s/RepoAudit@v1.0.0
        with:
          api-url: https://repoaudit-api.onrender.com
          timeout-seconds: "1200" # Increase to 20 minutes
          request-retries: "10"
```

---

[← Back to Main README](../readme.md)
