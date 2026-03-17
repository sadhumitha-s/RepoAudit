interface Props {
  score: number;
  summary: string;
  cached: boolean;
  commitHash: string | null;
}

function scoreColor(score: number): string {
  if (score >= 80) return "text-[#22c55e]"; // bright green
  if (score >= 50) return "text-[#facc15]"; // bright yellow
  return "text-[#ef4444]"; // bright red
}

function ringColor(score: number): string {
  if (score >= 80) return "stroke-[#22c55e]";
  if (score >= 50) return "stroke-[#facc15]";
  return "stroke-[#ef4444]";
}

export function ScoreCard({ score, summary, cached, commitHash }: Props) {
  const circumference = 2 * Math.PI * 54;
  const offset = circumference - (score / 100) * circumference;

  return (
    <div className="neo-card p-6 flex flex-col justify-center">
      <div className="flex flex-col sm:flex-row items-center gap-6">
        <div className="relative h-32 w-32 shrink-0">
          <svg className="h-full w-full -rotate-90" viewBox="0 0 120 120">
            <circle
              cx="60"
              cy="60"
              r="54"
              fill="none"
              stroke="#3f3f46"
              strokeWidth="12"
            />
            <circle
              cx="60"
              cy="60"
              r="54"
              fill="none"
              className={ringColor(score)}
              strokeWidth="12"
              strokeLinecap="square"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              style={{ transition: "stroke-dashoffset 1s ease" }}
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className={`text-4xl font-black ${scoreColor(score)}`}>
              {Math.round(score)}
            </span>
          </div>
        </div>

        <div className="space-y-3 text-center sm:text-left">
          <h2 className="text-xl font-bold uppercase tracking-wide text-white">Reproducibility Score</h2>
          <p className="text-base text-gray-400 font-medium">{summary}</p>
          <div className="flex flex-wrap justify-center sm:justify-start gap-3 mt-2">
            {cached && (
              <span className="neo-border bg-[#2563eb] px-3 py-1 text-xs font-bold uppercase tracking-wider text-white shadow-neo-sm">
                Cached
              </span>
            )}
            {commitHash && (
              <span className="neo-border bg-gray-800 px-3 py-1 font-mono text-xs font-bold text-gray-300 shadow-neo-sm">
                {commitHash.slice(0, 7)}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}