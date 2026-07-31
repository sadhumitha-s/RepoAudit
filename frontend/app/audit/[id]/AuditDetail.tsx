"use client";

import { useEffect, useState } from "react";
import { ScoreCard } from "@/components/ScoreCard";
import { RadarChart } from "@/components/RadarChart";
import { FixFeed } from "@/components/FixFeed";
import { ScoreHistory } from "@/components/ScoreHistory";
import { DecayCard } from "@/components/DecayCard";
import { PipelineGraph } from "@/components/PipelineGraph";
import { StatusIndicator } from "@/components/StatusIndicator";
import { getAudit, getAuditStatus, type AuditResponse } from "@/lib/api";

function parseGitHubUrl(url: string): { owner: string; repo: string } | null {
  const match = url.match(/github\.com\/([^/]+)\/([^/]+)/);
  if (!match) return null;
  return { owner: match[1], repo: match[2].replace(/\.git$/, "") };
}

export function AuditDetail({ id }: { id: string }) {
  const [audit, setAudit] = useState<AuditResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusProgress, setStatusProgress] = useState<string>("Loading audit results...");

  useEffect(() => {
    if (!id) return;

    let isMounted = true;
    let pollInterval: NodeJS.Timeout | null = null;
    let pollAttempts = 0;
    const MAX_POLLS = 300; // 15 minutes max at 3s intervals

    const loadAudit = async () => {
      try {
        const data = await getAudit(id);
        if (!isMounted) return;
        setAudit(data);

        if (data.status === "completed" || data.status === "failed") {
          setLoading(false);
        } else {
          // If still processing, start polling status
          setStatusProgress(data.status || "Queued...");
          startPolling();
        }
      } catch (err) {
        if (!isMounted) return;
        setError(err instanceof Error ? err.message : "Failed to load audit");
        setLoading(false);
      }
    };

    const pollStatus = async () => {
      try {
        pollAttempts++;
        if (pollAttempts > MAX_POLLS) {
          if (pollInterval) clearInterval(pollInterval);
          setError("Audit timed out. Please try again later.");
          setLoading(false);
          return;
        }

        const statusRes = await getAuditStatus(id);
        if (!isMounted) return;

        setStatusProgress(statusRes.progress || statusRes.status);

        if (statusRes.status === "completed" || statusRes.status === "failed") {
          if (pollInterval) clearInterval(pollInterval);
          // Fetch final data
          const finalData = await getAudit(id);
          if (isMounted) {
            setAudit(finalData);
            setLoading(false);
          }
        }
      } catch (err) {
        console.warn("Polling error:", err);
        // Don't kill polling on transient network errors
      }
    };

    const startPolling = () => {
      if (!pollInterval) {
        pollInterval = setInterval(pollStatus, 3000);
      }
    };

    setLoading(true);
    loadAudit();

    return () => {
      isMounted = false;
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [id]);

  if (loading || (audit && !audit.report && audit.status !== "failed")) {
    return <StatusIndicator progress={statusProgress} />;
  }

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
    <div className="space-y-6">
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

      <div className="grid gap-6 md:grid-cols-1">
        <PipelineGraph
          graph={
            audit.report.pipeline_graph ?? {
              nodes: [],
              edges: [],
              completeness_score: 0,
            }
          }
        />
      </div>

      {parsed && <ScoreHistory owner={parsed.owner} repo={parsed.repo} />}

      <FixFeed issues={allIssues} />
    </div>
  );
}
