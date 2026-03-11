"use client";

import { Loader2 } from "lucide-react";

interface Props {
  progress: string;
}

const STEPS = [
  { key: "queued", label: "Queued" },
  { key: "cloning", label: "Cloning" },
  { key: "ast_analysis", label: "AST Analysis" },
  { key: "semantic_audit", label: "Semantic Audit" },
  { key: "finalizing", label: "Finalizing" },
] as const;

/** Map backend progress text → active step index. */
function inferStep(progress: string): number {
  const lower = progress.toLowerCase();
  if (lower.includes("queue") || lower.includes("waiting")) return 0;
  if (lower.includes("clon")) return 1;
  if (lower.includes("static") || lower.includes("ast")) return 2;
  if (lower.includes("semantic")) return 3;
  if (lower.includes("scor") || lower.includes("final") || lower.includes("computing"))
    return 4;
  return 0;
}

export function StatusIndicator({ progress }: Props) {
  const activeStep = inferStep(progress);

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-sm">
      {/* Live status line */}
      <div className="mb-4 flex items-center gap-2">
        <Loader2 className="h-4 w-4 animate-spin text-brand-600" />
        <span className="text-sm font-medium text-[var(--foreground)]">
          {progress || "Processing..."}
        </span>
      </div>

      {/* Step progress bar */}
      <div className="flex items-start gap-1">
        {STEPS.map((step, i) => (
          <div
            key={step.key}
            className="flex flex-1 flex-col items-center gap-1.5"
          >
            <div
              className={`h-1.5 w-full rounded-full transition-colors duration-500 ${
                i <= activeStep ? "bg-brand-500" : "bg-[var(--border)]"
              }`}
            />
            <span
              className={`text-[11px] leading-tight ${
                i === activeStep
                  ? "font-semibold text-brand-700"
                  : i < activeStep
                    ? "font-medium text-brand-600"
                    : "text-[var(--muted)]"
              }`}
            >
              {step.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}