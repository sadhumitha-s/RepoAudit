const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:7860";

export interface Issue {
  rule: string;
  severity: "critical" | "warning" | "info";
  file: string;
  line: number | null;
  message: string;
  fix: string;
}

export interface CategoryScore {
  name: string;
  weight: number;
  score: number;
  issues: Issue[];
}

export interface DecayMetrics {
  shelf_life_days: number;
  time_to_break_days: number;
  decay_curve: { date: string; score: number }[];
}

export interface AuditReport {
  categories: CategoryScore[];
  total_score: number;
  summary: string;
  patch?: string;
  decay_metrics?: DecayMetrics;
}

export interface AuditResponse {
  audit_id: string;
  repo_url: string;
  status:
    | "queued"
    | "cloning"
    | "ast_analysis"
    | "semantic_audit"
    | "finalizing"
    | "completed"
    | "failed";
  commit_hash: string | null;
  score: number | null;
  report: AuditReport | null;
  created_at: string | null;
  cached: boolean;
}

export interface AuditStatusResponse {
  audit_id: string;
  status: AuditResponse["status"];
  progress: string;
}

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail || "Request failed");
  }

  return res.json();
}

export async function submitAudit(repoUrl: string): Promise<AuditResponse> {
  return request<AuditResponse>("/api/v1/audit", {
    method: "POST",
    body: JSON.stringify({ url: repoUrl }),
  });
}

export async function getAudit(auditId: string): Promise<AuditResponse> {
  return request<AuditResponse>(`/api/v1/audit/${encodeURIComponent(auditId)}`);
}

export async function getAuditStatus(
  auditId: string,
): Promise<AuditStatusResponse> {
  return request<AuditStatusResponse>(
    `/api/v1/audit/${encodeURIComponent(auditId)}/status`,
  );
}

// --- Score History ---

export interface ScoreHistoryPoint {
  audit_id: string;
  commit_hash: string;
  score: number;
  categories: CategoryScore[];
  created_at: string;
}

export interface ScoreHistoryResponse {
  owner: string;
  repo: string;
  points: ScoreHistoryPoint[];
}

export async function getScoreHistory(
  owner: string,
  repo: string,
): Promise<ScoreHistoryResponse> {
  return request<ScoreHistoryResponse>(
    `/api/v1/audit/history/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`,
  );
}