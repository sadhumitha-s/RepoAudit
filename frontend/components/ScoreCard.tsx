interface Props {
  score: number;
  summary: string;
  cached: boolean;
  commitHash: string | null;
}

function scoreColor(score: number): string {
  if (score >= 80) return "text-[var(--success)]";
  if (score >= 50) return "text-[var(--warning)]";
  return "text-[var(--destructive)]";
}

function ringColor(score: number): string {
  if (score >= 80) return "stroke-[var(--success)]";
  if (score >= 50) return "stroke-[var(--warning)]";
  return "stroke-[var(--destructive)]";
}

export function ScoreCard({ score, summary, cached, commitHash }: Props) {
  const circumference = 2 * Math.PI * 54;
  const offset = circumference - (score / 100) * circumference;

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-sm">
      <div className="flex items-center gap-6">
        <div className="relative h-32 w-32 shrink-0">
          <svg className="h-full w-full -rotate-90" viewBox="0 0 120 120">
            <circle
              cx="60"
              cy="60"
              r="54"
              fill="none"
              stroke="var(--border)"
              strokeWidth="8"
            />
            <circle
              cx="60"
              cy="60"
              r="54"
              fill="none"
              className={ringColor(score)}
              strokeWidth="8"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              style={{ transition: "stroke-dashoffset 1s ease" }}
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className={`text-3xl font-bold ${scoreColor(score)}`}>
              {Math.round(score)}
            </span>
          </div>
        </div>

        <div className="space-y-2">
          <h2 className="text-lg font-semibold">Reproducibility Score</h2>
          <p className="text-sm text-[var(--muted)]">{summary}</p>
          <div className="flex flex-wrap gap-2">
            {cached && (
              <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-700">
                Cached
              </span>
            )}
            {commitHash && (
              <span className="rounded-full bg-gray-100 px-2 py-0.5 font-mono text-xs text-gray-600">
                {commitHash.slice(0, 7)}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}