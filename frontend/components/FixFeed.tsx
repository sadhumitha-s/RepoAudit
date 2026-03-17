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
    bg: "bg-[#ef4444]", // Solid red
    border: "border-[#000000]",
    badge: "bg-black text-white",
    label: "CRITICAL",
  },
  warning: {
    icon: AlertTriangle,
    bg: "bg-[#facc15]", // Solid yellow
    border: "border-[#000000]",
    badge: "bg-black text-white",
    label: "WARNING",
  },
  info: {
    icon: Info,
    bg: "bg-[#3b82f6]", // Solid blue
    border: "border-[#000000]",
    badge: "bg-black text-white",
    label: "INFO",
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
    <div className={`border-2 ${config.border} ${config.bg} p-4 shadow-neo text-black`}>
      <div
        className="flex cursor-pointer items-start gap-3"
        onClick={() => setExpanded(!expanded)}
      >
        <Icon className="mt-0.5 h-5 w-5 shrink-0 stroke-[3]" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <span className={`px-2 py-1 text-xs font-bold uppercase tracking-wider ${config.badge}`}>
              {config.label}
            </span>
            <span className="bg-white px-2 py-1 text-xs font-bold font-mono border-2 border-black">
              {issue.rule}
            </span>
            {issue.file && (
              <span className="truncate font-mono text-xs font-bold bg-black/10 px-2 py-1 border-2 border-black/20">
                {issue.file}
                {issue.line != null && `:${issue.line}`}
              </span>
            )}
          </div>
          <p className="mt-1 text-base font-bold whitespace-pre-wrap">{issue.message}</p>
        </div>
        {issue.fix &&
          (expanded ? (
            <ChevronDown className="h-5 w-5 shrink-0 stroke-[3]" />
          ) : (
            <ChevronRight className="h-5 w-5 shrink-0 stroke-[3]" />
          ))}
      </div>

      {expanded && issue.fix && (
        <div className="mt-4 border-2 border-black bg-white p-4 shadow-neo-sm relative">
          <div className="flex items-start justify-between gap-4">
            <pre className="whitespace-pre-wrap text-sm font-mono font-bold text-black overflow-x-auto">
              {issue.fix}
            </pre>
            <button
              onClick={(e) => {
                e.stopPropagation();
                copyFix();
              }}
              className="shrink-0 bg-brand-accent border-2 border-black p-2 hover:-translate-y-0.5 transition-transform shadow-neo-sm active:translate-y-0 active:shadow-none"
              title="Copy fix"
            >
              {copied ? (
                <Check className="h-4 w-4 stroke-[3]" />
              ) : (
                <Copy className="h-4 w-4 stroke-[3]" />
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
      <div className="neo-card p-8 text-center text-lg font-bold uppercase tracking-wider text-brand-accent">
        NO ISSUES FOUND. THE REPOSITORY LOOKS REPRODUCIBLE!
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
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b-2 border-white pb-4">
        <h2 className="text-xl font-black uppercase tracking-wide text-white">Fix Feed</h2>
        <div className="flex flex-wrap gap-3 text-sm font-bold uppercase tracking-widest text-[#a1a1aa]">
          {critical > 0 && (
            <span className="text-[#ef4444]">
              {critical} CRITICAL
            </span>
          )}
          {warnings > 0 && (
            <span className="text-[#facc15]">
              {warnings} WARNINGS
            </span>
          )}
          <span>{issues.length} TOTAL</span>
        </div>
      </div>
      <div className="space-y-4">
        {sorted.map((issue, i) => (
          <IssueCard key={`${issue.rule}-${issue.file}-${issue.line}-${i}`} issue={issue} />
        ))}
      </div>
    </div>
  );
}