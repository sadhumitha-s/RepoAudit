"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AuditForm } from "@/components/AuditForm";
import { StatusIndicator } from "@/components/StatusIndicator";
import { ScoreCard } from "@/components/ScoreCard";
import { RadarChart } from "@/components/RadarChart";
import { FixFeed } from "@/components/FixFeed";
import {
  submitAudit,
  getAudit,
  getAuditStatus,
  type AuditResponse,
} from "@/lib/api";

export default function HomePage() {
  const [audit, setAudit] = useState<AuditResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);
  const [progress, setProgress] = useState("");

  async function handleSubmit(url: string) {
    setError(null);
    setAudit(null);
    setLoading(true);
    setPolling(false);
    setProgress("");

    try {
      const result = await submitAudit(url);

      if (result.status === "completed") {
        setAudit(result);
        setLoading(false);
        return;
      }

      // Start polling
      setPolling(true);
      setProgress("Queued...");
      await pollForResult(result.audit_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setLoading(false);
      setPolling(false);
    }
  }

  async function pollForResult(auditId: string) {
    const maxAttempts = 60;
    const interval = 2000;

    for (let i = 0; i < maxAttempts; i++) {
      await new Promise((r) => setTimeout(r, interval));

      try {
        const status = await getAuditStatus(auditId);
        setProgress(status.progress);

        if (status.status === "completed") {
          const full = await getAudit(auditId);
          setAudit(full);
          setLoading(false);
          setPolling(false);
          return;
        }

        if (status.status === "failed") {
          setError("Analysis failed. The repository may be inaccessible or too large.");
          setLoading(false);
          setPolling(false);
          return;
        }
      } catch {
        // Transient error, keep polling
      }
    }

    setError("Analysis timed out. Please try again.");
    setLoading(false);
    setPolling(false);
  }

  const allIssues =
    audit?.report?.categories.flatMap((c) => c.issues) ?? [];

  return (
    <div className="space-y-8">
      <section className="text-center">
        <h1 className="mb-2 text-3xl font-bold tracking-tight">
          Audit Your ML Repository
        </h1>
        <p className="text-[var(--muted)]">
          Paste a public GitHub URL to get a reproducibility score with
          actionable fixes.
        </p>
      </section>

      <AuditForm onSubmit={handleSubmit} loading={loading} />

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {polling && <StatusIndicator progress={progress} />}

      {audit?.report && (
        <div className="space-y-6">
          <div className="grid gap-6 md:grid-cols-2">
            <ScoreCard
              score={audit.report.total_score}
              summary={audit.report.summary}
              cached={audit.cached}
              commitHash={audit.commit_hash}
            />
            <RadarChart categories={audit.report.categories} />
          </div>

          <FixFeed issues={allIssues} />
        </div>
      )}
    </div>
  );
}