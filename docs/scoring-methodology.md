# Reproducibility Scoring Methodology

RepoAudit calculates a reproducibility score ranging from **0 to 100**. This score is a weighted average of six categories, reflecting the overall "health" and reproducibility of an ML repository.

## Scoring Categories & Weights

| Category | Weight | Primary Audit Goal |
|---------|--------|---------------------|
| **Environment** | 15% | Reproducible environment setup (e.g., `requirements.txt`, Docker). |
| **Determinism** | 20% | Deterministic execution patterns (e.g., random seeds, fixed shuffles). |
| **Datasets** | 15% | Portable data handling and provenance (no hardcoded paths, live URLs). |
| **Semantic** | 20% | Alignment between documentation (README) and implementation. |
| **Execution** | 20% | Verifiable entry points and dynamic reproduction success (L0-L3). |
| **Documentation** | 10% | Presence of critical documentation sections. |

---

## 1. Environment (15%)
Scored based on the presence and quality of dependency management files.
- **Base Score: 100.**
- **Penalties:**
  - `-60` points if no dependency file (`requirements.txt`, `pyproject.toml`, etc.) is found.
  - `-30` points (weighted by ratio) for unpinned dependencies.
  - `-20` points if `requirements.txt` is present but contains no pinned versions.
  - Up to `-20` points for missing dependencies detected via import analysis.
  - Up to `-30` points for "Hardware Fingerprinting" (anti-sandbox/HW identification).
  - `-20` points for **each** yanked dependency found on PyPI.
  - `-10` points for **each** dependency with known CVEs.
- **Bonus:**
  - `+10` points (max 100) if a **Dockerfile** is provided.

## 2. Determinism (20%)
Focuses on patterns that introduce non-determinism into training or evaluation.
- **Base Score: 100.**
- **Penalties:**
  - `-40` points for each **Critical** determinism issue (e.g., unseeded `random.seed()`, `np.random.seed()`, `torch.manual_seed()`).
  - `-10` points for **Warnings** (e.g., non-deterministic `shuffle=True` in data loaders).
  - **Notebook Deep Analysis**:
    - `-20` points for **out-of-order execution** (variable used before definition in earlier cells).
    - `-10` points for **global state mutations** (top-level assignments/imports that impact reproducibility).
    - `-10` points for **non-reproducible installs** (e.g., `!pip install` inside cells).

## 3. Datasets (15%)
Evaluates the portability and accessibility of datasets.
- **Base Score: 100.**
- **Penalties:**
  - Up to `-50` points for **hardcoded absolute paths** (e.g., `/home/user/data/my_dataset`).
  - `-15` points for each missing data directory referenced in documentation.
  - Up to `-30` points for **Data Provenance** issues (broken URLs, gated datasets with no instructions).

## 4. Semantic (20%)
Checks if the repository's code matches its documentation using LLM analysis.
- **Rules:**
  - `0` score if no README is present.
  - `-15` points (max 60) for each file/directory mentioned in the README that is missing in the repo.
  - Penalizes **Configuration Drift**: Discrepancies between hyperparameters in README and actual code defaults.

## 5. Execution (20%)
Combines static entry-point detection with dynamic execution replay verification.
- **Static Check (30% weight of category):**
  - Points awarded for common entry points: `main.py`, `train.py`, `run.py`, `app.py`, `Makefile`, `setup.py`, `pyproject.toml`.
- **Dynamic Replay (70% weight of category):**
  - **L0 (25 pts):** Dependencies install successfully.
  - **L1 (50 pts):** Main entry point can be imported and initialized.
  - **L2 (80 pts):** Entry point runs for >5 seconds without crashing.
  - **L3 (100 pts):** Execution produces expected output (files/logs).

## 6. Documentation (10%)
Assesses the structural quality of project documentation.
- **Rules:**
  - `0` score if no README is present.
  - Balanced points for three mandatory sections: **Installation**, **Usage**, **Datasets**.
  - Verified using semantic section detection (not just keyword matching).

---

## Overall Summary
RepoAudit provides a textual summary based on the total score:
- **Total ≥ 80:** "Repository has good reproducibility practices."
- **Total ≥ 50:** "Repository needs improvement."
- **Total < 50:** "Significant reproducibility concerns."

---

## Multi-Repository Comparative Analysis

When multiple repositories are compared, RepoAudit identifies a **Golden Standard** implementation.

### The Golden Standard Logic
The Golden Standard implementation is determined by:
1. **Highest Aggregate Score**: The primary metric for comparison.
2. **Execution Tier**: Tied scores are broken by the highest achieved Replay Verification level (L0–L3).
3. **Reproducibility Shelf-life**: If execution tiers are also tied, the repository with the longest predicted shelf-life (lowest decay) is selected.

This benchmarking allows researchers to quickly identify the most robust implementation among competing versions of the same research paper or project.

---

[← Back to Main README](../readme.md)
