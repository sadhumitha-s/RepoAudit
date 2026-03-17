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
    <div className="neo-card p-6 flex flex-col">
      {/* Live status line */}
      <div className="mb-6 flex items-center gap-3 border-b-2 border-[#3f3f46] pb-4">
        <Loader2 className="h-6 w-6 animate-spin text-brand-accent" />
        <span className="text-base font-bold uppercase tracking-wider text-white">
          {progress || "PROCESSING..."}
        </span>
      </div>

      {/* Step progress bar */}
      <div className="flex items-start gap-2">
        {STEPS.map((step, i) => (
          <div
            key={step.key}
            className="flex flex-1 flex-col items-center gap-2"
          >
            <div
              className={`h-3 w-full border-2 border-black transition-colors duration-500 shadow-neo-sm ${
                i <= activeStep ? "bg-brand-accent" : "bg-[#3f3f46]"
              }`}
            />
            <span
              className={`text-xs text-center font-bold uppercase tracking-wider ${
                i === activeStep
                  ? "text-brand-accent"
                  : i < activeStep
                    ? "text-white"
                    : "text-gray-500"
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