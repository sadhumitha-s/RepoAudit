"use client";

import { useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  Info,
  Copy,
  Check,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import type { Issue } from "@/lib/api";

interface Props {
  issues: Issue[];
}

const SEVERITY_CONFIG = {
  critical: {
    icon: AlertCircle,
    bg: "bg-red-50",
    border: "border-red-200",
    badge: "bg-red-100 text-red-700",
    label: "Critical",
  },
  warning: {
    icon: AlertTriangle,
    bg: "bg-amber-50",
    border: "border-amber-200",
    badge: "bg-amber-100 text-amber-700",
    label: "Warning",
  },
  info: {
    icon: Info,
    bg: "bg-blue-50",
    border: "border-blue-200",
    badge: "bg-blue-100 text-blue-700",
    label: "Info",
  },
} as const;

function IssueCard({ issue }: { issue: Issue }) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const config = SEVERITY_CONFIG[issue.severity] || SEVERITY_CONFIG.info;
  const Icon = config.icon;

  async function copyFix() {
    if (!issue.fix) return;
    await navigator.clipboard.writeText(issue.fix);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className={`rounded-lg border ${config.border} ${config.bg} p-4`}>
      <div
        className="flex cursor-pointer items-start gap-3"
        onClick={() => setExpanded(!expanded)}
      >
        <Icon className="mt-0.5 h-4 w-4 shrink-0 opacity-70" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className={`rounded-full px-2 py-0.5 text-xs ${config.badge}`}>
              {config.label}
            </span>
            <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
              {issue.rule}
            </span>
            {issue.file && (
              <span className="truncate font-mono text-xs text-[var(--muted)]">
                {issue.file}
                {issue.line != null && `:${issue.line}`}
              </span>
            )}
          </div>
          <p className="mt-1 text-sm">{issue.message}</p>
        </div>
        {issue.fix &&
          (expanded ? (
            <ChevronDown className="h-4 w-4 shrink-0 text-[var(--muted)]" />
          ) : (
            <ChevronRight className="h-4 w-4 shrink-0 text-[var(--muted)]" />
          ))}
      </div>

      {expanded && issue.fix && (
        <div className="mt-3 ml-7 rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
          <div className="flex items-start justify-between gap-2">
            <pre className="whitespace-pre-wrap text-xs text-[var(--foreground)]">
              {issue.fix}
            </pre>
            <button
              onClick={(e) => {
                e.stopPropagation();
                copyFix();
              }}
              className="shrink-0 rounded p-1 hover:bg-gray-100"
              title="Copy fix"
            >
              {copied ? (
                <Check className="h-3.5 w-3.5 text-[var(--success)]" />
              ) : (
                <Copy className="h-3.5 w-3.5 text-[var(--muted)]" />
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export function FixFeed({ issues }: Props) {
  if (issues.length === 0) {
    return (
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 text-center text-sm text-[var(--muted)]">
        No issues found. The repository looks reproducible!
      </div>
    );
  }

  const sorted = [...issues].sort((a, b) => {
    const order = { critical: 0, warning: 1, info: 2 };
    return (order[a.severity] ?? 3) - (order[b.severity] ?? 3);
  });

  const critical = sorted.filter((i) => i.severity === "critical").length;
  const warnings = sorted.filter((i) => i.severity === "warning").length;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Fix Feed</h2>
        <div className="flex gap-3 text-xs text-[var(--muted)]">
          {critical > 0 && (
            <span className="text-[var(--destructive)]">
              {critical} critical
            </span>
          )}
          {warnings > 0 && (
            <span className="text-[var(--warning)]">{warnings} warnings</span>
          )}
          <span>{issues.length} total</span>
        </div>
      </div>
      {sorted.map((issue, i) => (
        <IssueCard key={`${issue.rule}-${issue.file}-${issue.line}-${i}`} issue={issue} />
      ))}
    </div>
  );
}