"use client";

import { useState } from "react";
import { AuditForm } from "@/components/AuditForm";
import { StatusIndicator } from "@/components/StatusIndicator";
import { ScoreCard } from "@/components/ScoreCard";
import { RadarChart } from "@/components/RadarChart";
import { FixFeed } from "@/components/FixFeed";
import { ScoreHistory } from "@/components/ScoreHistory";
import {
  submitAudit,
  getAudit,
  getAuditStatus,
  type AuditResponse,
} from "@/lib/api";

function parseGitHubUrl(url: string): { owner: string; repo: string } | null {
  const match = url.match(/github\.com\/([^/]+)\/([^/]+)/);
  if (!match) return null;
  return { owner: match[1], repo: match[2].replace(/\.git$/, "") };
}

export default function HomePage() {
  const [audit, setAudit] = useState<AuditResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);
  const [progress, setProgress] = useState("");
  const [copyStatus, setCopyStatus] = useState<"idle" | "copied" | "failed">("idle");

  async function handleSubmit(url: string) {
    setError(null);
    setAudit(null);
    setLoading(true);
    setPolling(false);
    setProgress("");
    setCopyStatus("idle");

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

  function getPermalinkUrl(auditId: string): string {
    if (typeof window === "undefined") return `/audit/${auditId}`;
    return `${window.location.origin}/audit/${auditId}`;
  }

  function openPermalink(auditId: string) {
    window.open(`/audit/${auditId}`, "_blank", "noopener,noreferrer");
  }

  async function copyPermalink(auditId: string) {
    try {
      await navigator.clipboard.writeText(getPermalinkUrl(auditId));
      setCopyStatus("copied");
      setTimeout(() => setCopyStatus("idle"), 2000);
    } catch {
      setCopyStatus("failed");
      setTimeout(() => setCopyStatus("idle"), 2000);
    }
  }

  const allIssues = audit?.report?.categories.flatMap((c) => c.issues) ?? [];
  const parsed = audit?.repo_url ? parseGitHubUrl(audit.repo_url) : null;

  return (
    <div className="space-y-12">
      <section className="text-center mt-8">
        <h1 className="mb-4 text-5xl md:text-6xl font-black tracking-tighter uppercase">
          Audit Your <span className="text-brand-accent">ML</span> Repository
        </h1>
        <p className="text-lg text-gray-400 font-medium max-w-2xl mx-auto">
          Paste a public GitHub URL to get a reproducibility score with
          actionable fixes.
        </p>
      </section>

      <AuditForm onSubmit={handleSubmit} loading={loading} />

      {error && (
        <div className="neo-border bg-red-500 text-white p-4 text-base font-bold shadow-neo">
          ERROR: {error}
        </div>
      )}

      {polling && <StatusIndicator progress={progress} />}

      {audit?.report && (
        <div className="space-y-12 animate-in fade-in duration-500">
          <div className="flex flex-wrap items-center gap-4 border-b-2 border-white pb-6">
            <button
              onClick={() => openPermalink(audit.audit_id)}
              className="neo-button px-4 py-2 text-sm bg-white"
            >
              VIEW PERMALINK
            </button>
            <button
              onClick={() => copyPermalink(audit.audit_id)}
              className="neo-button px-4 py-2 text-sm bg-white flex items-center gap-2"
            >
              {copyStatus === "copied" ? "COPIED!" : "COPY LINK"}
            </button>
            {copyStatus === "failed" && (
              <span className="text-sm font-bold text-red-500 bg-red-500/10 px-2 py-1 neo-border">COPY FAILED</span>
            )}
          </div>

          <div className="grid gap-8 md:grid-cols-2">
            <ScoreCard
              score={audit.report.total_score}
              summary={audit.report.summary}
              cached={audit.cached}
              commitHash={audit.commit_hash}
            />
            <RadarChart categories={audit.report.categories} />
          </div>

          {parsed && <ScoreHistory owner={parsed.owner} repo={parsed.repo} />}

          <FixFeed issues={allIssues} />

          {audit.report.patch && (
            <div className="border-2 border-white bg-black p-6 shadow-neo mt-8 text-left">
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-4 gap-4">
                <div>
                  <h2 className="text-xl font-black uppercase tracking-wide text-white">Auto-Remediation Patch</h2>
                  <p className="text-sm font-bold text-[#a1a1aa] mt-1 uppercase">Apply this patch to automatically resolve findings deterministically via AST modification.</p>
                </div>
                <button
                  onClick={() => {
                    const blob = new Blob([audit.report!.patch!], { type: "text/plain" });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = "concrete.patch";
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                  }}
                  className="neo-button px-4 py-2 text-sm bg-brand-accent text-black"
                >
                  DOWNLOAD PATCH
                </button>
              </div>
              <pre className="p-4 bg-[#111] text-[#e5e5e5] text-sm overflow-x-auto border-2 border-white font-mono max-h-96 overflow-y-auto">
                {audit.report.patch}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}