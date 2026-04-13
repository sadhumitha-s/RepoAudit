"use client";

import { useEffect, useState } from "react";
import { ScoreCard } from "@/components/ScoreCard";
import { RadarChart } from "@/components/RadarChart";
import { FixFeed } from "@/components/FixFeed";
import { ScoreHistory } from "@/components/ScoreHistory";
import { DecayCard } from "@/components/DecayCard";
import { PipelineGraph } from "@/components/PipelineGraph";
import { StatusIndicator } from "@/components/StatusIndicator";
import { getAudit, type AuditResponse } from "@/lib/api";

function parseGitHubUrl(url: string): { owner: string; repo: string } | null {
  const match = url.match(/github\.com\/([^/]+)\/([^/]+)/);
  if (!match) return null;
  return { owner: match[1], repo: match[2].replace(/\.git$/, "") };
}

  const [audit, setAudit] = useState<AuditResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  console.log("Audit Status:", audit?.status);
  console.log("PGR Data received:", audit?.report?.pipeline_graph);
  console.log("PGR Nodes:", audit?.report?.pipeline_graph?.nodes?.length);
  console.log("Decay Data received:", audit?.report?.decay_metrics);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    getAudit(id)
      .then(setAudit)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load audit"))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <StatusIndicator progress="Loading audit results..." />;

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {error}
      </div>
    );
  }

  if (!audit?.report) {
    return (
      <div className="text-center text-[var(--muted)]">
        {audit?.status === "failed"
          ? "This audit failed. The repository may be inaccessible."
          : "Audit is still processing..."}
      </div>
    );
  }

  const allIssues = audit.report.categories.flatMap((c) => c.issues);
  const parsed = audit.repo_url ? parseGitHubUrl(audit.repo_url) : null;

  return (
      <div>
        <h1 className="text-2xl font-bold">Audit Results</h1>
        {audit.repo_url && (
          <p className="text-sm text-[var(--muted)]">{audit.repo_url}</p>
        )}
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <ScoreCard
          score={audit.report.total_score}
          summary={audit.report.summary}
          cached={audit.cached}
          commitHash={audit.commit_hash}
        />
        <RadarChart categories={audit.report.categories} />
      </div>

      {audit.report.decay_metrics && (
        <div className="grid gap-6 md:grid-cols-1">
          <DecayCard metrics={audit.report.decay_metrics} />
        </div>
      )}

      {audit.report.pipeline_graph && (
        <div className="grid gap-6 md:grid-cols-1">
          <PipelineGraph graph={audit.report.pipeline_graph} />
        </div>
      )}

      {parsed && <ScoreHistory owner={parsed.owner} repo={parsed.repo} />}

      <FixFeed issues={allIssues} />
    </div>
  );
}