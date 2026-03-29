# Multi-Repository Comparative Analysis

RepoAudit allows you to compare reproducibility metrics across multiple implementations of the same model or paper. This is specifically designed for:
- **Paper Reviewers**: Quickly verify which implementation of a submitted paper is the most robust.
- **Reproducibility Chairs**: Benchmark multiple implementations (e.g., from a challenge or competition) side-by-side.
- **Researchers**: Audit their own implementation against state-of-the-art baselines.

## How it Works

1. **URL Resolution**: Submit up to 5 GitHub repository URLs.
2. **Parallel Auditing**: RepoAudit triggers/fetches audits for all repositories in parallel.
3. **Overlaid Radar Chart**: Metrics are aggregated into a single 6-axis radar chart using `recharts`. Each repository is represented by a unique color layer.
4. **Leaderboard**: A "Top Performer" (Golden Standard) is identified based on the highest aggregate reproducibility score.
5. **Detailed Metrics**: Individual ScoreCards for each repository are displayed for granular issue comparison.

## API Usage

### Compare Repositories
`POST /api/v1/compare`

**Request Body:**
```json
{
  "urls": [
    "https://github.com/owner/repo-a",
    "https://github.com/owner/repo-b"
  ]
}
```

**Response:**
A list of `AuditResponse` objects. If an audit is not yet complete, the `status` field will indicate `queued`, `cloning`, etc.

## UI Navigation

Access the comparison dashboard by clicking **"Compare"** in the top navigation bar or visiting `/compare` directly.
- Add URLs using the "Add Another Implementation" button.
- Click "Initialize Combat Analysis" to start the benchmarking.
- The UI will automatically poll for results until all audits are completed.

## Limitations
- **Max Repositories**: Currently limited to 5 repositories per comparison to maintain chart readability.
- **Visual Overlap**: With 5 repositories, the radar chart can become "busy". Use the legend to toggle visibility or focus on the Top Performer.
