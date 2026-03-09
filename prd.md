# Product Requirements Document: RepoAudit 2.0

## 1. Executive Summary

**Product:** RepoAudit  
**Version:** 2.0  
**Type:** Open Source Research Infrastructure Tool  
**Status:** MVP Planning / Technical Specification  

RepoAudit is an automated platform that analyzes public machine learning research repositories to evaluate reproducibility. Version 2.0 introduces deep logic verification using Abstract Syntax Tree (AST) analysis to verify execution flow and Large Language Models (LLMs) to perform semantic audits of documentation and synthesize actionable fixes.

**Goal:** Bridge the "reproducibility gap" in AI research by providing researchers with a CPU-efficient, high-integrity tool to audit code and documentation before publication.

---

## 2. Product Vision & Problem Statement

### 2.1 Vision

To become the industry standard for "Reproducibility Readiness" in ML research, serving as a prerequisite check for major AI conferences and journals to ensure scientific transparency.

### 2.2 Problem Statement

Current ML research publications frequently suffer from "Silent Failures" in reproducibility:

**Logical non-determinism:** Seeding code is present in the repository but is never actually invoked in the training loop or main execution flow.

**Documentation Drift:** README files describe scripts, parameters, or datasets that have been moved, renamed, or deleted in the source code.

**Environment Decay:** Missing or unpinned dependencies prevent code from running shortly after publication.

**Hardcoding:** Absolute local paths or hidden environment configurations make code non-portable across different machines.

---

## 3. Target Audience

**Primary:** ML Researchers (Academic & Corporate) who need to verify their repository is "reviewer-ready" and fully reproducible.

**Secondary:** Conference Artifact Reviewers who require an automated, high-integrity score to triage and evaluate submitted repositories.

**Secondary:** Open Source Maintainers who wish to ensure that community contributions do not degrade the reproducibility of the project.

---

## 4. Technical Stack & Infrastructure (Zero-Cost FOSS)

### 4.1 Core Stack

**Frontend:** Next.js 14 (App Router, TypeScript), React, Tailwind CSS, Lucide React (Icons), Shadcn/UI (Components).

**Backend API:** FastAPI (Asynchronous Python 3.11+).

**Task Management:** Celery (Distributed Task Queue) for handling long-running repository analysis.

**Message Broker:** Redis (Internal sidecar for task state and Celery communication).

**Primary Database:** PostgreSQL (Hosted via Supabase for report history and issue tracking).

**Caching Layer:** Redis (Internal instance for Commit-Hash-based result caching).

### 4.2 Analysis Engine & AI

**Static Analysis:** Native Python regex and pathlib for structural checks.

**Logic Analysis:** Python ast module (Abstract Syntax Tree) for deep logic verification and libcst for code modification suggestions.

**AI Layer:** Groq API (utilizing Llama-3-70B) for sub-second, semantic verification of documentation and fix synthesis.

**Deployment:** Hugging Face Spaces (Persistent CPU tier for API/Worker) and Vercel (Static Frontend).

---

## 5. Functional Requirements (P0)

### 5.1 Commit-Hash Caching System

**Requirement:** The system must not consume resources re-analyzing identical code states.

**Logic:** Upon submission, the API resolves the latest GitHub commit_hash.

**Action:** If the commit_hash exists in the cache (Redis/Postgres), the system serves the existing JSON report instantly without triggering a worker task.

---

### 5.2 GitHub Repository Cloner

**Requirement:** Robust, shallow cloning of public repositories.

**Constraints:** Maximum repo size limit (e.g., 200MB) to ensure stability on free-tier infrastructure and prevent memory exhaustion.

---

### 5.3 The "Intelligence" Rule Engine

#### Category A: Determinism Verification (AST Analysis)

**The Check:** Moving beyond string matching to verify logical execution.

**AST Logic:** Parse all .py files using the Python ast module. Locate Call nodes to seeding functions (PyTorch, NumPy, Random). Verify the call is "Reachable" (global scope or within the if __name__ == "__main__": entry point).

**Scoring:** High penalty if random operations are detected without a logically reachable seed.

---

#### Category B: Semantic Documentation Audit (AI-Driven)

**The Check:** Cross-reference README claims with the actual File System.

**Logic:** LLM parses README.md to extract claimed data directories (e.g., /data/raw) and entry points (e.g., bash run.sh).

**Verification:** The system performs a look-up to check if those paths/files exist. Discrepancies generate a "Semantic Mismatch" warning.

---

#### Category C: Dependency Synthesis (AI-Driven)

**The Check:** Automated generation of missing or incomplete requirements.txt.

**Logic:** Static analysis identifies all import statements. AI filters standard library vs. external packages and generates a requirements.txt with version recommendations based on current PyPI metadata.

---

#### Category D: Hardcoded Path Detection

**The Check:** Identify non-portable strings.

**Logic:** Scan for strings matching common local path patterns (e.g., C:\Users\, /home/user/, Documents/).

---

## 6. Scoring Engine & Heuristics

Repositories receive a reproducibility score from 0–100.

| Category | Weight | Criteria |
|--------|--------|--------|
| Environment | 20% | Presence of pinned requirements.txt, environment.yml, or Dockerfile. |
| Determinism | 20% | AST-verified seeding for PyTorch, NumPy, and Python Random. |
| Datasets | 20% | Documentation of download links and absence of hardcoded local paths. |
| Semantic Logic | 20% | AI-verified alignment between README instructions and repository structure. |
| Execution | 10% | Presence of standard entry points (train.py, Makefile, main.py). |
| Documentation | 10% | Presence of "Installation", "Datasets", and "Usage" sections in README. |

---

## 7. User Interface (Web Dashboard)

### 7.1 Audit Submission

Single-input field for GitHub URLs.

Real-time status indicator:  
Queued -> Cloning -> AST Analysis -> Semantic Audit -> Finalizing.

---

### 7.2 Result View

**Score Card:** Large circular gauge with weighted reproducibility score.

**Category Breakdown:** Radar chart showing performance across the six audit categories.

**The Fix Feed:** A prioritized list of issues with AI-suggested code patches and copy-to-clipboard functionality.

**Structure View:** Highlighting specific files where hardcoded paths or missing logic were detected.

---

## 8. Non-Functional Requirements

### 8.1 Performance

**Latency:** Analysis of a standard research repository must complete under 90 seconds.

**Concurrency:** The system must handle up to 50 concurrent requests, with a worker queue managing serial/parallel clones based on CPU availability.

---

### 8.2 Security (Static Analysis Sandbox)

**Execution Policy:** Strictly No Code Execution. The worker only performs static parsing and AST walking.

**Network Isolation:** Workers have restricted outbound access, limited to GitHub and metadata APIs (PyPI).

---

### 8.3 Reliability

**Retry Logic:** Exponential backoff for GitHub API rate limits.

**Resource Cleanup:** Automated purging of ephemeral clone directories immediately following report generation.

---

## 9. Definition of Done (DoD)

- [ ] System successfully clones public repositories under 200MB.
- [ ] Redis/Database cache returns results for identical commit hashes in <200ms.
- [ ] AST engine correctly identifies missing or unreachable seeds in multi-file projects.
- [ ] Semantic audit flags mismatches between README text and file structure.
- [ ] Dashboard renders actionable fixes for environment and hardcoding issues.
- [ ] Full system is deployed as a FOSS stack on Hugging Face Spaces and Vercel.

---

## 10. Future Roadmap

**CI/CD Integration:** A GitHub Action that runs RepoAudit on every Pull Request to ensure reproducibility isn't degraded during development.

**Multi-language Support:** Expanding AST analysis to R, Julia, and C++ for broader scientific research coverage.

**Badge System:** Dynamic SVG badges for READMEs displaying the RepoAudit score.